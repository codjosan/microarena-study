"""Research tools: no third-party dependencies, no future access, reproducible inference."""
from collections import defaultdict
import math,random,statistics

def pct_change(xs):
    return [xs[i]/xs[i-1]-1 for i in range(1,len(xs)) if xs[i-1]>0]

def ewma(xs,decay=0.94):
    if not 0<decay<1:raise ValueError('decay out of range')
    v=None;out=[]
    for x in xs:
        if not math.isfinite(x):raise ValueError('non-finite value')
        v=x if v is None else decay*v+(1-decay)*x
        out.append(v)
    return out

def rolling_vol(returns,lookback=50):
    if lookback<2:raise ValueError('lookback must be >=2')
    result=[]
    for i in range(len(returns)):
        window=returns[max(0,i-lookback+1):i+1]
        result.append(statistics.stdev(window) if len(window)>1 else 0.)
    return result

def imbalance_signal(book):
    bid=max(0,book['bid_depth']);ask=max(0,book['ask_depth'])
    return (bid-ask)/(bid+ask) if bid+ask else 0.

def order_flow_imbalance(rows,lookback=20):
    recent=rows[-lookback:]
    buy=sum(r['market_buy_qty'] for r in recent)
    sell=sum(r['market_sell_qty'] for r in recent)
    return (buy-sell)/max(1,buy+sell)

def queue_fill_estimate(queue_ahead,quantity,trade_flow):
    """Counterfactual queue fill under no cancellations and fixed price priority."""
    if min(queue_ahead,quantity,trade_flow)<0:raise ValueError('negative queue parameters')
    return min(quantity,max(0,int(trade_flow-queue_ahead)))

def markout(fill,marks,horizon=10):
    """Signed markout: positive implies a price move favorable to filled maker."""
    t=fill['tick_id'];s=fill['symbol']
    if t+horizon not in marks or t not in marks:return None
    side=1 if fill['side']=='buy' else -1
    return side*(marks[t+horizon][s]-fill['price'])*fill['qty']

def markout_table(fills,marks,horizons=(1,5,20)):
    result={}
    for h in horizons:
        vals=[markout(f,marks,h) for f in fills if f['liquidity']=='maker']
        vals=[v for v in vals if v is not None]
        result[str(h)]={'count':len(vals),'avg_usd':sum(vals)/len(vals) if vals else None,
                        'total_usd':sum(vals)}
    return result

def pnl_reconcile(cash,inventory,marks,equity,tolerance=1e-5):
    calculated=cash+sum(inventory.get(s,0)*marks[s] for s in marks)
    return {'calculated_equity':calculated,'reported_equity':equity,
            'difference':calculated-equity,'passed':abs(calculated-equity)<=tolerance}

def inventory_var(inventory,marks,vols,z=2.326):
    """Diagonal volatility VaR approximation, not a tail guarantee."""
    var=sum((inventory.get(s,0)*marks[s]*vols.get(s,0))**2 for s in marks)
    return z*math.sqrt(var)

def block_bootstrap_mean(xs,block=20,replicates=500,seed=20261123):
    """Non-IID moving-block bootstrap for noisy tick-level realized PnL."""
    if block<1 or replicates<10:raise ValueError('invalid bootstrap size')
    if not xs:raise ValueError('empty observations')
    if any(not math.isfinite(x) for x in xs):raise ValueError('nonfinite PnL')
    rng=random.Random(seed);n=len(xs)
    estimates=[]
    for _ in range(replicates):
        sample=[]
        while len(sample)<n:
            idx=rng.randrange(n)
            sample.extend(xs[(idx+j)%n] for j in range(block))
        estimates.append(sum(sample[:n])/n)
    estimates.sort()
    return {'mean':sum(xs)/n,'lower_95':estimates[int(.025*(replicates-1))],
            'upper_95':estimates[int(.975*(replicates-1))],
            'replicates':replicates,'block':block}

def quote_activity(orders,fills):
    counts=defaultdict(int)
    for o in orders:counts[o['event']]+=1
    volume=sum(f['qty'] for f in fills)
    return {'messages':dict(counts),'fills':len(fills),'filled_shares':volume,
            'submissions_per_fill':counts['submit']/max(1,len(fills)),
            'cancellations_per_fill':counts['request_cancel']/max(1,len(fills))}

def by_venue(fills):
    grouped=defaultdict(lambda:{'fill_events':0,'shares':0,'fees':0.,'notional':0.})
    for f in fills:
        a=grouped[f['venue']];a['fill_events']+=1;a['shares']+=f['qty'];a['fees']+=f['fee']
        a['notional']+=f['qty']*f['price']
    return dict(grouped)
