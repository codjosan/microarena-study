# Offline Market Stream and Stress Scenario Dictionary

## Files

`data/market_stream.csv` has one row for each `(tick_id,symbol,venue)`: 2,400 ticks × 3 symbols × 2 venues = **14,400 rows**.

| Column | Units and interpretation |
|---|---|
| `tick_id` | Simulated decision time, 5 seconds between ticks |
| `symbol` | ALPHA / BETA / GAMMA |
| `venue` | NORTH / SOUTH |
| `bid`, `ask` | Prices (ask strictly above bid) |
| `bid_depth`, `ask_depth` | Shares displayed at best bid/ask |
| `market_buy_qty` | Completed aggressive buy volume reaching the ask during tick |
| `market_sell_qty` | Completed aggressive sell volume reaching the bid during tick |
| `imbalance` | Synthetic order-book imbalance proxy [-1,1] |
| `latency_ticks` | Minimum order acknowledgement/hedge delay in ticks |
| `stale` | Observable stale market indicator; execution blocked |
| `halted` | Venue/instrument trading disabled; execution blocked |

`data/reference_marks.csv` has the synthetic reference mid used for inventory marking. `data/manifest.json` provides instrument tick sizes and public split boundaries. Real market regimes and generator source are **not included**.

## Stress catalogue

Scenario definitions are in `src/microarena/scenarios.py`. The package includes fifteen deterministic scenarios (one base plus fourteen adverse cases):

`base`, `fees_3x`, `spread_3x`, `depth_20pct`, `latency_plus_5`, `cancel_delay_plus_8`, `north_down`, `south_down`, `flow_30pct`, `flow_250pct`, `toxic_flow_4x`, `mark_gap_minus_300bps`, `mark_gap_plus_300bps`, `combined_crisis`, and `combined_toxic`.

Each scenario changes the same base tape through independently specified knobs. Some shocks are deliberately artificial worst-case sensitivity tests and do not form a stochastic forecast. Report which scenarios are mechanically difficult and which are economically credible.

## Split-use rules

- Train ticks 0–1199: research and tuning.
- Validation ticks 1200–1799: model selection without repeated opportunistic optimization.
- Test ticks 1800–2399: held-out evaluation window.

Keep test-period values strictly held out from parameter calibration and policy selection.
