import argparse, json
from pathlib import Path
from .engine import Engine
from .metrics import summarize
from .scenarios import config_for,SCENARIOS
from .strategy import CandidateStrategy
from .baseline import NaiveSymmetricMaker

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',default='data');p.add_argument('--out',default='outputs/candidate')
    p.add_argument('--strategy',choices=['candidate','baseline'],default='candidate')
    p.add_argument('--scenario',choices=list(SCENARIOS),default='base')
    a=p.parse_args()
    strat=CandidateStrategy() if a.strategy=='candidate' else NaiveSymmetricMaker()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    result=Engine(a.data,config_for(a.scenario)).run(strat,out)
    summary=summarize(result)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
