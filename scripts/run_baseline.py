from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from microarena.engine import Engine
from microarena.baseline import NaiveSymmetricMaker
from microarena.scenarios import config_for
from microarena.metrics import summarize
for case in ('base','fees_3x','combined_crisis','north_down'):
    out=ROOT/'outputs'/('baseline' if case=='base' else 'baseline_'+case)
    result=Engine(ROOT/'data',config_for(case)).run(NaiveSymmetricMaker(),out)
    metrics=summarize(result)
    (out/'summary.json').write_text(json.dumps(metrics,indent=2))
    print(case,'validation',metrics['validation']['net_return_pct'],'test',metrics['test']['net_return_pct'],
          'maker fills',metrics['maker_fills'])
