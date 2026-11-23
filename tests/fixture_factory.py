"""Tiny *independent* fixture maker for unit tests, not the hidden market-data DGP."""
from pathlib import Path
import csv,json,random

def generate(out,seed=87,n=65):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    symbols={'ALPHA':[100,0.01],'BETA':[45,0.01],'GAMMA':[210,0.05]}
    venues=['NORTH','SOUTH'];rng=random.Random(seed)
    rows=[];marks=[]
    for t in range(n):
        for sym,(base,tick) in symbols.items():
            mid=base+tick*(t//5+rng.randint(-7,7))
            marks.append({'tick_id':t,'symbol':sym,'reference_mid':mid})
            for v in venues:
                spread=2*tick
                bid=round((mid-tick)/tick)*tick
                rows.append({'tick_id':t,'symbol':sym,'venue':v,'bid':round(bid,4),
                    'ask':round(bid+spread,4),'bid_depth':rng.randint(20,90),
                    'ask_depth':rng.randint(20,90),'market_buy_qty':rng.randint(15,75),
                    'market_sell_qty':rng.randint(15,75),'imbalance':round(rng.uniform(-1,1),5),
                    'latency_ticks':1 if v=='NORTH' else 2,'stale':0,'halted':0})
    for name,items in [('market_stream.csv',rows),('reference_marks.csv',marks)]:
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
    (out/'manifest.json').write_text(json.dumps({'seed':seed,'ticks':n,'symbols':symbols,
        'venues':venues,'rows':len(rows),'train_end':1199,'validation_end':1799,
        'tick_seconds':5,'synthetic':True},indent=2))
