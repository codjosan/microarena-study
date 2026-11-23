"""Independent post-run fill toxicity, quote activity and bootstrap diagnostics."""
import argparse,csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from microarena.research import markout_table,quote_activity,by_venue,block_bootstrap_mean
from microarena.data import load_data
p=argparse.ArgumentParser()
p.add_argument('--run',default='outputs/baseline');p.add_argument('--output',default=None)
a=p.parse_args()
folder=ROOT/a.run
with (folder/'fills.csv').open(newline='') as f:fills=list(csv.DictReader(f))
with (folder/'orders.csv').open(newline='') as f:orders=list(csv.DictReader(f))
with (folder/'equity.csv').open(newline='') as f:daily=list(csv.DictReader(f))
for x in fills:
    for k in ('qty','tick_id','order_id'):x[k]=int(x[k])
    for k in ('price','fee'):x[k]=float(x[k])
_,_,marks=load_data(ROOT/'data')
equity=[float(r['equity']) for r in daily]
pnl=[equity[0]-1_000_000]+[equity[i]-equity[i-1] for i in range(1,len(equity))]
report={'toxicity_markouts':markout_table(fills,marks),'quote_activity':quote_activity(orders,fills),
        'venue_attribution':by_venue(fills),
        'block_bootstrap_tick_pnl':block_bootstrap_mean(pnl,block=30,replicates=300),
        'equity_reconciliation':{'sum_tick_pnl':sum(pnl),'end_minus_start':equity[-1]-1_000_000}}
out=Path(a.output) if a.output else folder/'research_diagnostics.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
