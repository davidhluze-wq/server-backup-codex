#!/usr/bin/env python3
"""Local, data-free feasibility spike for LANA Commodity Autopilot.

This is not a trading strategy or a backtest. It measures a deterministic local
paper-ledger replay and NautilusTrader runtime initialization without a provider,
broker, or market-data connection.
"""
from __future__ import annotations

import hashlib
import json
import math
import resource
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "results.json"
SYMBOLS = (
    "CL", "NG", "GC", "SI", "HG", "ZC", "ZW", "ZS", "ZM", "ZL",
    "CC", "KC", "CT", "SB", "LE", "HE", "PL", "PA", "HO", "RB",
)
BARS = 756


def synthetic_close(symbol_index: int, bar: int) -> float:
    """Stable pseudo-price; it deliberately does not resemble a market feed."""
    return 100.0 + symbol_index * 1.7 + bar * 0.015 + math.sin(bar / 9 + symbol_index) * 1.3


def replay_ledger() -> dict:
    started = time.perf_counter()
    rows: list[str] = []
    positions = 0
    realized = 0.0
    fees = 0.0
    for idx, symbol in enumerate(SYMBOLS):
        closes = [synthetic_close(idx, bar) for bar in range(BARS)]
        position = 0
        entry = 0.0
        for bar in range(60, BARS):
            fast = sum(closes[bar - 20:bar]) / 20
            slow = sum(closes[bar - 60:bar]) / 60
            desired = 1 if fast > slow else 0
            if desired != position:
                price = closes[bar]
                fees += 1.25
                if position:
                    realized += price - entry
                elif desired:
                    entry = price
                rows.append(f"{symbol}|{bar}|{position}>{desired}|{price:.6f}")
                position = desired
        if position:
            realized += closes[-1] - entry
        positions += position
    digest = hashlib.sha256("\n".join(rows).encode()).hexdigest()
    return {
        "symbols": len(SYMBOLS),
        "bars_per_symbol": BARS,
        "events": len(rows),
        "open_positions": positions,
        "realized_before_fees": round(realized, 6),
        "fees": round(fees, 6),
        "digest": digest,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def nautilus_engine_smoke() -> dict:
    started = time.perf_counter()
    # Test-kit FX data is used only to prove engine construction. It is not commodity data.
    with open("/dev/null", "w", encoding="utf-8") as null, redirect_stdout(null), redirect_stderr(null):
        import nautilus_trader
        from nautilus_trader.test_kit.providers import TestInstrumentProvider
        from nautilus_trader.test_kit.stubs.component import TestComponentStubs

        engine = TestComponentStubs.backtest_engine(
            instrument=TestInstrumentProvider.default_fx_ccy("AUD/USD"),
        )
        engine.dispose()
    return {
        "version": getattr(nautilus_trader, "__version__", "unknown"),
        "synthetic_instrument_only": True,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def main() -> None:
    first = replay_ledger()
    second = replay_ledger()
    if first["digest"] != second["digest"]:
        raise RuntimeError("non-deterministic ledger replay")
    data = {
        "purpose": "local feasibility only; no external data, broker, keys, or orders",
        "ledger": first | {"replay_deterministic": True},
        "nautilus": nautilus_engine_smoke(),
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "decision": "Nautilus remains a candidate until real licensed futures data proves roll, multiplier, fill and replay behavior.",
    }
    RESULT.write_text(json.dumps(data, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=True))


if __name__ == "__main__":
    main()
