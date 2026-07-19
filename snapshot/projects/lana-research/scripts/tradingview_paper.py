#!/usr/bin/env python3
"""TradingView webhook ingestion for LANA paper research.

The module accepts alerts as evidence-only paper signals. It contains no broker
connector, no account credentials, and no path to create a live order.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    import psycopg2 as pg
except ImportError:
    import psycopg as pg

ROOT = Path(os.environ.get("LANA_ROOT", Path.home() / "lana-research"))
SCHEMA_FILE = ROOT / "sql" / "phase3_tradingview.sql"
DEFAULT_ACCOUNT = "lana-tradingview-paper"
SENSITIVE_KEYS = re.compile(r"token|secret|password|api[_-]?key|authorization", re.I)
VALID_ACTIONS = {"buy", "sell", "long", "short", "close", "exit"}


def _db():
    return pg.connect(os.environ["DATABASE_URL"])


def configured() -> bool:
    return bool(os.environ.get("TRADINGVIEW_WEBHOOK_TOKEN", "").strip())


def verify_token(candidate: str) -> bool:
    expected = os.environ.get("TRADINGVIEW_WEBHOOK_TOKEN", "").strip()
    return bool(expected) and hmac.compare_digest(expected, candidate or "")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items() if not SENSITIVE_KEYS.search(str(k))}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    if isinstance(value, str):
        return value[:1000]
    return value


def ensure_schema(conn) -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()


def bootstrap_account(initial_equity: float = 10_000.0) -> dict[str, Any]:
    if initial_equity <= 0:
        raise ValueError("initial_equity must be positive")
    conn = _db()
    try:
        ensure_schema(conn)
        cur = conn.cursor()
        cur.execute(
            """insert into lana.paper_accounts(name,currency,initial_equity)
               values(%s,'USD',%s)
               on conflict(name) do update set active=true
               returning id,name,currency,initial_equity""",
            (DEFAULT_ACCOUNT, initial_equity),
        )
        row = cur.fetchone()
        cur.execute("select 1 from lana.pnl_snapshots where mode='paper' limit 1")
        if not cur.fetchone():
            cur.execute(
                """insert into lana.pnl_snapshots(equity,realized,unrealized,open_positions,win_rate,mode)
                   values(%s,0,0,0,0,'paper')""",
                (initial_equity,),
            )
        conn.commit()
        return {"id": row[0], "name": row[1], "currency": row[2], "initial_equity": row[3]}
    finally:
        conn.close()


def _required_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _as_price(payload: dict[str, Any]) -> float:
    raw = _required_text(payload, "price", "close", "last", "market_price")
    try:
        price = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("alert requires a positive price/close value") from exc
    if price <= 0:
        raise ValueError("alert requires a positive price/close value")
    return price


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    symbol = _required_text(payload, "symbol", "ticker", "market").upper()
    action = _required_text(payload, "action", "side", "strategy_order_action").lower()
    if not symbol or len(symbol) > 120:
        raise ValueError("alert requires a valid symbol/ticker")
    if action not in VALID_ACTIONS:
        raise ValueError("action must be buy, sell, long, short, close, or exit")
    price = _as_price(payload)
    strategy = _required_text(payload, "strategy", "strategy_name", "name") or "TradingView alert"
    event_time = _required_text(payload, "event_id", "id", "time", "timestamp", "bar_time")
    cleaned = _sanitize(payload)
    fingerprint = json.dumps(
        {"symbol": symbol, "action": action, "price": price, "strategy": strategy, "event_time": event_time},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    event_key = _required_text(payload, "event_id", "id") or hashlib.sha256(fingerprint.encode()).hexdigest()
    return {
        "event_key": event_key[:180],
        "symbol": symbol,
        "action": action,
        "price": price,
        "strategy": strategy[:240],
        "event_time": event_time[:120],
        "payload": cleaned,
    }


def ingest(payload: dict[str, Any]) -> dict[str, Any]:
    event = normalize(payload)
    conn = _db()
    try:
        ensure_schema(conn)
        cur = conn.cursor()
        cur.execute(
            """insert into lana.webhook_events(provider,event_key,payload,status)
               values('tradingview',%s,%s,'received')
               on conflict(event_key) do nothing returning id""",
            (event["event_key"], json.dumps(event["payload"])),
        )
        inserted = cur.fetchone()
        if not inserted:
            cur.execute("select signal_id,status from lana.webhook_events where event_key=%s", (event["event_key"],))
            existing = cur.fetchone()
            conn.commit()
            return {"ok": True, "duplicate": True, "signal_id": existing[0], "status": existing[1]}

        event_id = inserted[0]
        side = "BUY" if event["action"] in {"buy", "long"} else "SELL"
        evidence = {
            "provider": "tradingview",
            "event_key": event["event_key"],
            "strategy": event["strategy"],
            "event_time": event["event_time"],
            "quality_gate": "research-pass",
            "paper_only": True,
            "payload": event["payload"],
        }
        cur.execute(
            """insert into lana.signals(market,question,prob_estimate,market_price,edge,confidence,
               side,thesis,evidence,status,mode)
               values(%s,%s,null,%s,null,null,%s,%s,%s,'open','paper') returning id""",
            (
                event["symbol"], f"TradingView {event['action']} alert from {event['strategy']}",
                event["price"], side,
                "TradingView paper alert awaiting Strategy/Signal Quality Gate.",
                json.dumps(evidence),
            ),
        )
        signal_id = cur.fetchone()[0]
        cur.execute(
            "update lana.webhook_events set status='accepted', signal_id=%s where id=%s",
            (signal_id, event_id),
        )
        conn.commit()
        return {"ok": True, "duplicate": False, "signal_id": signal_id, "status": "accepted"}
    except Exception as exc:
        conn.rollback()
        raise ValueError(str(exc)[:200]) from exc
    finally:
        conn.close()


def status() -> dict[str, Any]:
    out = {"configured": configured(), "account": None, "accepted_events": 0, "last_received_at": None}
    try:
        conn = _db()
        try:
            ensure_schema(conn)
            cur = conn.cursor()
            cur.execute("select name,currency,initial_equity,active from lana.paper_accounts where name=%s", (DEFAULT_ACCOUNT,))
            row = cur.fetchone()
            if row:
                out["account"] = {"name": row[0], "currency": row[1], "initial_equity": row[2], "active": row[3]}
            cur.execute("select count(*),max(received_at) from lana.webhook_events where provider='tradingview' and status='accepted'")
            count, received = cur.fetchone()
            out["accepted_events"] = count
            out["last_received_at"] = received.isoformat() if received else None
        finally:
            conn.close()
    except Exception as exc:
        out["error"] = str(exc)[:150]
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LANA TradingView paper webhook helper")
    parser.add_argument("action", choices=["bootstrap", "status", "validate"])
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--payload", help="JSON payload for validate")
    args = parser.parse_args()
    if args.action == "bootstrap":
        print(json.dumps(bootstrap_account(args.initial_equity), ensure_ascii=False))
    elif args.action == "status":
        print(json.dumps(status(), ensure_ascii=False))
    else:
        if not args.payload:
            parser.error("validate requires --payload")
        print(json.dumps(normalize(json.loads(args.payload)), ensure_ascii=False))
