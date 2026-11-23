# Strategy API and event-clock semantics

## Interface

Implement `CandidateStrategy.on_tick(ctx) -> Decision` in `src/microarena/strategy.py`.

Return `Decision(quotes=[Quote(symbol,venue,side,price,qty),...], hedges=[Hedge(symbol,venue,side,qty),...])`.

- `side`: exactly `'buy'` or `'sell'`.
- Price must be a positive finite tick-multiple, **passive** against the current venue best quote (`buy <= bid`, `sell >= ask`). Off-tick, crossed, and oversized quotes are rejected and counted.
- `qty` must be a positive integer. A hedge is an aggressive order, not a target inventory.
- Each `(symbol, venue, side)` may have at most one outstanding quote; a desired quote that differs from the existing outstanding quote requests cancellation, whose acknowledgement is **delayed**. A replacement is not accepted before the existing order disappears.
- Quotes not present in the new `Decision` request cancellation. **Never assume a cancellation instantly removes fill risk.**
- `ctx.live_orders` includes outstanding pending/live orders; track them to avoid order spam and to manage risk.

## Context fields

| Name | Semantics |
|---|---|
| `tick_id` | Current tick integer |
| `book[(symbol,venue)]` | Current completed snapshot and flow; quote and halt flags |
| `history[(symbol,venue)]` | Current and past snapshots, up to 100 observations, never future |
| `mark[symbol]` | Current reference mid, never future |
| `inventory[symbol]` | Position after this tick's previously placed fills |
| `cash`, `equity`, `peak_equity`, `drawdown` | Current marked account state |
| `live_orders` | Read-only snapshot of pending/live orders |
| `recent_fills` | Most recent completed fills |
| `symbols`, `venues` | Instrument and venue names |

## Per-tick lifecycle

1. Current market snapshot is read; pending cancellation acknowledgements and order activations are applied.
2. Previously submitted hedge requests that have completed venue latency execute at current best quotes plus impact and taker fee, subject to health, liquidity and risk limits.
3. Live resting maker quotes may fill against aggressive trade flow at current touch, after depletion of their queue-ahead position.
4. The completed snapshot, inventory, and fills become visible to `on_tick`.
5. The strategy sends new **passive** quote intents, change/cancel requests and optional hedges.
6. These messages become effective **only after simulated venue latency**. The current tick is never tradable at decision time, even via hedge requests.
7. Account equity is marked and logged. The engine charges maker/taker fees and includes terminal inventory liquidation.

This is a discrete-tick approximation: queue priority is stylized, hidden liquidity and partial venue matching are simplified, cross-venue basis is synthetic, and hedges assume delayed market orders at the future best price.

## Accounting

`equity = cash + sum(inventory_shares[s] * mark[s])`.

Maker fill of a buy of `q` at `p`: `cash -= q*p + fee`, `inventory += q`. Sell reverses the signs. A negative maker fee means a rebate. Taker fills pay spread, fee and nonlinear impact.

Terminal equity subtracts an explicit estimated taker fee for any unliquidated inventory. Verify PnL by reconciling mark changes, fills and cash flows. The simulator does not pay financing/borrow and does not impose margin interest, which is a limitation to discuss in the report.

## Research hazards

- A quote that was passive at submission may become unfavorable before activation. Engine only matches an order when it coincides with the current best passive quote; other stale-priced orders remain and must be canceled.
- High trade flow can deplete the queue, but market impact and adverse selection change expected markout.
- A policy can appear profitable by accumulating inventory near the end; terminal unwind and drawdown must be included.
- Observing completed flow at tick `t` is legal; executing an order created at `t` against that same flow is not.
