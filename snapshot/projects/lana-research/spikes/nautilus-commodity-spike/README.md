# Nautilus Commodity Spike

This isolated spike measures only local feasibility on the current VPS.

- `run_spike.py` replays deterministic synthetic bars through a tiny local paper ledger.
- It initializes/disposes a NautilusTrader backtest engine with an included synthetic FX test
  instrument, only to measure runtime readiness.
- It does not claim commodity compatibility: no licensed futures data, roll logic, multiplier,
  fill model, provider key, broker, Docker service, or live order is used.

Pass conditions for any next phase are: deterministic ledger replay; bounded VPS resource use;
then a separate licensed-data test proving contract roll, multiplier, settlement/next-session
fills, fees/slippage, audit log and repeatable replay.

The current result schema records ledger `events`, not a generic `trade_count`; external
verification scripts must validate the fields emitted by `run_spike.py`.

Provider SDKs used for later proof-of-data checks are installed only in this isolated virtual
environment after their presence is explicitly verified; they are not assumed to be bundled with
the engine dependency.
