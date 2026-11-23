from .types import Decision

class CandidateStrategy:
    """Implement a profitable risk-aware inventory-constrained quoting strategy.

    on_tick(ctx) -> Decision:
       ctx.tick_id, ctx.book[(symbol,venue)], ctx.history[(symbol,venue)]
       ctx.inventory[symbol], ctx.cash, ctx.equity, ctx.peak_equity
       ctx.live_orders (read-only snapshot), ctx.mark[symbol], ctx.symbols, ctx.venues
       ctx.drawdown, ctx.recent_fills

    Data is available only through tick_id. Missing keys in desired quotes imply
    cancel request; live/cancel messages incur latency. No regime/split label.
    See docs/STRATEGY_API.md for next-tick activation and fill semantics.
    """
    def on_tick(self,ctx):
        return Decision()
