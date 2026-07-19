# TradingView Paper Alerts

This integration receives TradingView alerts as LANA paper signals. It cannot log in to a
TradingView account, cannot read an account balance, and cannot place broker orders.

## Security model

- Use a dedicated HTTPS hostname on port 443. TradingView webhooks do not deliver to port 8811.
- Generate a random `TRADINGVIEW_WEBHOOK_TOKEN` and keep it only in the protected runtime environment.
- Put the token only in the webhook URL, never in the JSON body, Pine Script, Git, logs, or screenshots.
- The receiver accepts a JSON alert, removes secret-shaped fields, deduplicates retries, and creates a
  `paper` signal with `quality_gate=research-pass`. It does not create a trade.
- TradingView's price is stored as a market price, not as a prediction-market probability. It cannot be
  used for LANA's probability edge or fractional-Kelly sizing until a separate price model is validated.
- TradingView can retry server failures, so every alert must include a stable `event_id`.

## Alert endpoint

```
https://YOUR_LANA_DOMAIN/api/tradingview/webhook/YOUR_RANDOM_TOKEN
```

## Alert JSON template

Use valid JSON in TradingView's alert message field:

```json
{
  "event_id": "{{ticker}}-{{interval}}-{{time}}-{{strategy.order.id}}",
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": "{{close}}",
  "time": "{{time}}",
  "strategy": "YOUR_STRATEGY_NAME"
}
```

For indicator alerts without strategy order placeholders, provide a stable ID built from ticker,
interval, time, and the condition name. The receiver accepts `buy`, `sell`, `long`, `short`, `close`,
and `exit` actions.

## Activation sequence

1. Create a DNS hostname for LANA and configure an HTTPS reverse proxy to `127.0.0.1:8811`.
   This server uses `david-lana.duckdns.org`; run `sudo bash
   /home/david_master/lana-research/deploy/enable-tradingview-caddy.sh` once from an administrator
   shell. It installs Caddy, requests the certificate, and opens only HTTP/HTTPS when UFW is active.
2. Put `TRADINGVIEW_WEBHOOK_TOKEN` in the protected service environment and restart only the LANA
   dashboard service.
3. Run `tradingview_paper.py bootstrap` once to create the local USD paper account.
4. Test the endpoint locally, then create one TradingView alert with the JSON above.
5. Confirm that the signal appears in the LANA dashboard as `paper` and `research-pass`.
6. Promote only independently validated strategies to `paper-watch`; a webhook alert alone never
   qualifies a trade.
