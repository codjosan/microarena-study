from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from microarena.engine import Engine
from microarena.strategy import CandidateStrategy
from microarena.baseline import NaiveSymmetricMaker
from microarena.metrics import summarize
from microarena.scenarios import SCENARIOS,config_for
p=argparse.ArgumentParser()
p.add_argument('--strategy',choices=['candidate','baseline'],default='candidate')
a=p.parse_args()
out=ROOT/'outputs'/f'{a.strategy}_stress';out.mkdir(parents=True,exist_ok=True)
results={}
for name in SCENARIOS:
    strategy=CandidateStrategy() if a.strategy=='candidate' else NaiveSymmetricMaker()
    result=Engine(ROOT/'data',config_for(name)).run(strategy)
    results[name]=summarize(result)
    print(name,results[name]['validation']['net_return_pct'],results[name]['test']['net_return_pct'])
(out/'stress_results.json').write_text(json.dumps(results,indent=2))
