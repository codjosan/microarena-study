from .types import Decision, Quote, Hedge

class NaiveSymmetricMaker:
    """Baseline: passive top-of-book quoting, modest sizes, limited inventory skew."""
    def on_tick(self,ctx):
        quotes=[]; hedges=[]
        for symbol in ctx.symbols:
            inv=ctx.inventory.get(symbol,0)
            for venue in ctx.venues:
                r=ctx.book[(symbol,venue)]
                if r['stale'] or r['halted']: continue
                size=25
                if inv<100: quotes.append(Quote(symbol,venue,'buy',r['bid'],size))
                if inv>-100: quotes.append(Quote(symbol,venue,'sell',r['ask'],size))
            if abs(inv)>105:
                v=ctx.venues[0]
                if not ctx.book[(symbol,v)]['stale'] and not ctx.book[(symbol,v)]['halted']:
                    hedges.append(Hedge(symbol,v,'sell' if inv>0 else 'buy',min(30,abs(inv))))
        return Decision(quotes,hedges)
