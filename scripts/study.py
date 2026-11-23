"""Offline eight-hour research study ledger and milestone gate.
This is a local audit aid for tracking experimental stages, revisions, and test runs.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/'outputs'/'study_ledger.jsonl'
STRATEGY=ROOT/'src'/'microarena'/'strategy.py'
STAGES=[
 ('01','Feed audit and microstructure hypothesis'),
 ('02','Queue dynamics and fill probability'),
 ('03','Inventory control and risk limits'),
 ('04','Multi-venue order placement and cancel races'),
 ('05','Adverse selection and latency'),
 ('06','Validation and sensitivity analysis'),
 ('07','Blind test and adversarial stress'),
 ('08','Reproducibility, attribution and final defense'),
]
PROMPTS=[
 'Audit the stream for spread, depth, imbalance, outages, and latency. Which signals are observable at decision time?',
 'Explain how your quote prices, queue positions, and maker fills differ from simply buying/selling at mid.',
 'Estimate conditional fill probability. Quantify queue-ahead sensitivity with a reproducible experiment.',
 'Implement inventory skew and explain how it behaves when one-sided aggressive flow persists.',
 'Find a way to avoid excessive cancel/replace messages while preserving quote competitiveness.',
 'Identify a cancellation race and write a test that reproduces it without relying on luck.',
 'Demonstrate how the market maker would behave if NORTH were unavailable for 300 ticks.',
 'Explain a causal adverse-selection indicator and show its effect net of execution costs.',
 'Stress your strategy with five additional latency ticks and explain unexpected fills.',
 'Quantify whether taker hedges actually improve net outcomes versus inventory risk.',
 'Estimate spread capture separately from mark-to-market drift and fees.',
 'Propose two alternative market-making policies and evaluate them with empirical evidence.',
 'Give a no-lookahead proof based on the event clock and available context fields.',
 'Tune using training data and report validation results cleanly without peeking at the final test window.',
 'Demonstrate reproducibility: same inputs should yield bit-for-bit equivalent summaries.',
 'Show what fails under the combined liquidity, spread, and latency crisis.',
 'Run the locked test one time for final evaluation, then defend unexpected results.',
 'Present a concise risk committee memo and identify unmodeled exchange mechanics.',
 'Challenge your initial explanation with counter-evidence and revised implementation.',
 'Show why high order volume with low fill volume is not a good execution policy.',
 'Prove all inventory, gross notional, and drawdown controls under extreme flow.',
 'Build a negative control using shuffled observations or an intentionally poor policy.',
 'Measure uncertainty with block bootstrap on tick-level PnL, without claiming independence.',
 'Identify one simulator simplification and propose a minimally invasive validation experiment.',
 'Demonstrate a forced hedge following inventory accumulation and explain realized spread costs.',
 'Audit whether stressed observations may inadvertently leak future data.',
 'Explain why terminal inventory liquidation belongs in net PnL.',
 'Evaluate the strategy from a risk-management perspective focused on tail risk rather than Sharpe alone.',
 'Find and fix a defect, add a regression test, and show before/after outputs.',
 'Summarize which hypotheses failed and what you would prioritize in a real deployment.'
]

def utcnow():return datetime.now(timezone.utc)
def hashfile(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def file_set_digest(paths):
    return hashlib.sha256(event_canonical([(str(p.relative_to(ROOT)),hashfile(p)) for p in sorted(paths)]).encode()).hexdigest()

def evaluator_fingerprint():
    protected=[ROOT/'src'/'microarena'/name for name in ('engine.py','types.py','data.py','metrics.py','scenarios.py')]
    protected += [ROOT/'data'/name for name in ('market_stream.csv','reference_marks.csv','manifest.json')]
    return file_set_digest(protected)

def code_fingerprint():
    return file_set_digest((ROOT/'src'/'microarena').rglob('*.py'))

def event_canonical(event):return json.dumps(event,sort_keys=True,separators=(',',':'))
def events():
    if not STATE.exists():return []
    return [json.loads(line) for line in STATE.read_text().splitlines() if line.strip()]

def check_chain(seq):
    prior='0'*64
    for idx,event in enumerate(seq):
        core={k:v for k,v in event.items() if k!='digest'}
        if core.get('prev')!=prior or core.get('seq')!=idx:
            raise ValueError(f'ledger chain mismatch at event {idx}')
        calc=hashlib.sha256(event_canonical(core).encode()).hexdigest()
        if calc!=event.get('digest'):
            raise ValueError(f'ledger digest mismatch at event {idx}')
        prior=event['digest']
    return True

def append(kind,**payload):
    seq=events();check_chain(seq)
    core={'seq':len(seq),'at':utcnow().isoformat(),'kind':kind,'prev':seq[-1]['digest'] if seq else '0'*64,'data':payload}
    core['digest']=hashlib.sha256(event_canonical(core).encode()).hexdigest()
    STATE.parent.mkdir(parents=True,exist_ok=True)
    with STATE.open('a') as f:f.write(event_canonical(core)+'\n')
    print(f'RECORDED #{core["seq"]} {kind}')
    return core

def require_started():
    seq=events();check_chain(seq)
    if not seq or seq[0]['kind']!='start':raise ValueError('run `python scripts/study.py start` first')
    return seq

def read_metrics():
    p=ROOT/'outputs'/'candidate'/'summary.json'
    if not p.exists():return None
    return json.loads(p.read_text())

def status(seq=None):
    seq=seq if seq is not None else require_started()
    start=datetime.fromisoformat(seq[0]['at']);hours=(utcnow()-start).total_seconds()/3600
    kinds=[e['kind'] for e in seq]
    approvals=[e['data']['stage'] for e in seq if e['kind']=='approve']
    last_review=[e for e in seq if e['kind']=='review']
    counts={'elapsed_hours':round(hours,3),'prompts':kinds.count('prompt'),
            'reviewed_responses':len(last_review),'rejections':sum(e['data']['decision']=='reject' for e in last_review),
            'revisions':kinds.count('revision'),'test_runs':kinds.count('test_run'),
            'approvals':approvals,'score':max([e['data']['score'] for e in seq if e['kind']=='score'] or [0]),
            'final_test_runs':kinds.count('final_test'),'chain_ok':check_chain(seq)}
    return counts

def gates():
    seq=require_started();stat=status(seq);fail=[]
    for key,limit in [('elapsed_hours',8),('reviewed_responses',16),('rejections',2),('revisions',4),('test_runs',8),('score',80)]:
        if stat[key]<limit:fail.append(f'{key}: {stat[key]} < {limit}')
    if len(set(stat['approvals']))<8:fail.append('all 8 stages require milestone sign-off')
    # Stage approvals must have been made no earlier than their scheduled hour.
    started=datetime.fromisoformat(seq[0]['at'])
    for i,(number,_) in enumerate(STAGES):
        approvals=[e for e in seq if e['kind']=='approve' and e['data']['stage']==number]
        if not approvals:continue
        elapsed=(datetime.fromisoformat(approvals[-1]['at'])-started).total_seconds()/3600
        if elapsed<i:fail.append(f'stage {number} approved prematurely at {elapsed:.2f} h (requires {i} h)')
    if stat['final_test_runs']!=1:fail.append('exactly one final_test must be recorded')
    scores=[e for e in seq if e['kind']=='score']
    if not scores or not scores[-1]['data'].get('approved'):
        fail.append('final score must be explicitly signed off')
    tests=[e for e in seq if e['kind']=='test_run']
    if tests and not tests[-1]['data'].get('passed'):fail.append('latest test must pass')
    revisions=[e['data']['sha256'] for e in seq if e['kind']=='revision']
    if len(set(revisions))<4:fail.append('four distinct revision hashes required')
    if revisions and hashfile(STRATEGY)!=revisions[-1]:fail.append('strategy changed after last revision record')
    if seq[0]['data'].get('evaluator_sha256')!=evaluator_fingerprint():
        fail.append('protected evaluator or dataset changed after study start')
    if tests and tests[-1]['data'].get('test_count',0)<90:
        fail.append('at least 90 total tests required (80 bundled + >=10 strategy-authored)')
    metric=read_metrics()
    if not metric:fail.append('candidate summary missing: run candidate before final_test')
    else:
        for split in ('validation','test'):
            if metric[split]['net_return_pct']<=0:fail.append(f'{split} net return not positive')
            if metric[split]['max_drawdown_pct']>6:fail.append(f'{split} drawdown over 6%')
        if metric['maker_fills']<120:fail.append('maker fills below 120')
        if metric['filled_shares']<2000:fail.append('filled shares below 2000')
        if metric['submitted']>25000:fail.append('more than 25,000 quote submissions')
        if metric['violations'].get('post_trade_limit',0)>0:fail.append('post-trade portfolio limit breached')
    scenario_path=ROOT/'outputs'/'candidate_stress'/'stress_results.json'
    if not scenario_path.exists():fail.append('candidate stress results missing')
    else:
        scenarios=json.loads(scenario_path.read_text())
        if len(scenarios)<len(__import__('microarena.scenarios',fromlist=['SCENARIOS']).SCENARIOS):
            fail.append('not all required adversarial scenarios assessed')
        for scenario,stats in scenarios.items():
            if stats['all']['max_drawdown_pct']>6:fail.append(f'{scenario}: max drawdown exceeded 6%')
            if stats['violations'].get('post_trade_limit',0)>0:fail.append(f'{scenario}: inventory/gross limit breach')
    final=[e for e in seq if e['kind']=='final_test']
    if final:
        f=final[0]['data']
        if metric and f['summary_sha256']!=hashfile(ROOT/'outputs'/'candidate'/'summary.json'):
            fail.append('candidate final summary changed after blind test')
        if f['strategy_sha256']!=hashfile(STRATEGY):fail.append('candidate code changed after blind test')
        if f['code_sha256']!=code_fingerprint():fail.append('supporting source code changed after blind test')
        if scenario_path.exists() and f['stress_sha256']!=hashfile(scenario_path):fail.append('stress evidence changed after blind test')
    return stat,fail

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('start')
    p=sub.add_parser('prompt');p.add_argument('--number',type=int)
    p=sub.add_parser('review');p.add_argument('--file',required=True);p.add_argument('--decision',choices=['accept','reject'],required=True);p.add_argument('--feedback',required=True)
    sub.add_parser('revision');sub.add_parser('test');sub.add_parser('status')
    p=sub.add_parser('approve');p.add_argument('--stage',required=True);p.add_argument('--notes',required=True)
    p=sub.add_parser('score');p.add_argument('--value',type=int,required=True);p.add_argument('--approve',action='store_true');p.add_argument('--notes',required=True)
    sub.add_parser('final-test');sub.add_parser('finalize')
    a=ap.parse_args()
    try:
        if a.cmd=='start':
            if STATE.exists():raise ValueError('study exists; do not reset a live session')
            append('start',package='microarena-1.0',strategy_sha256=hashfile(STRATEGY),evaluator_sha256=evaluator_fingerprint())
        elif a.cmd=='prompt':
            seq=require_started()
            idx=a.number if a.number is not None else (sum(e['kind']=='prompt' for e in seq)%len(PROMPTS))+1
            if not 1<=idx<=len(PROMPTS):raise ValueError('prompt number out of range')
            print(f'\nPROMPT {idx:02d}: {PROMPTS[idx-1]}\n')
            append('prompt',number=idx,text=PROMPTS[idx-1])
        elif a.cmd=='review':
            require_started();p=Path(a.file)
            if not p.is_file() or not p.read_text().strip():raise ValueError('response evidence file missing or empty')
            append('review',response_sha256=hashfile(p),response_file=str(p),decision=a.decision,feedback=a.feedback)
        elif a.cmd=='revision':
            require_started();append('revision',sha256=hashfile(STRATEGY))
        elif a.cmd=='test':
            require_started()
            env=dict(__import__('os').environ);env['PYTHONPATH']=str(ROOT/'src')
            cmd=[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v']
            run=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True)
            print(run.stdout[-1000:]);print(run.stderr[-3500:])
            import re
            matched=re.search(r'Ran (\d+) tests',run.stderr)
            count=int(matched.group(1)) if matched else 0
            append('test_run',passed=run.returncode==0,returncode=run.returncode,test_count=count,output_sha256=hashlib.sha256((run.stdout+run.stderr).encode()).hexdigest())
            if run.returncode:raise ValueError('test suite failed')
        elif a.cmd=='approve':
            seq=require_started()
            stage=a.stage.zfill(2)
            if stage not in dict(STAGES):raise ValueError('unknown stage')
            earlier=[st for st,_ in STAGES if int(st)<int(stage)]
            if any(st not in [e['data']['stage'] for e in seq if e['kind']=='approve'] for st in earlier):
                raise ValueError('approve stages in order')
            started=datetime.fromisoformat(seq[0]['at']);hours=(utcnow()-started).total_seconds()/3600
            if hours<int(stage)-1:raise ValueError('stage earliest approval hour not yet reached')
            append('approve',stage=stage,notes=a.notes)
        elif a.cmd=='score':
            require_started()
            if not 0<=a.value<=100:raise ValueError('score must be 0-100')
            append('score',score=a.value,director_approved=a.approve,notes=a.notes)
        elif a.cmd=='status':
            print(json.dumps(status(),indent=2))
        elif a.cmd=='final-test':
            seq=require_started()
            if any(e['kind']=='final_test' for e in seq):raise ValueError('final test already recorded')
            if seq[0]['data'].get('evaluator_sha256')!=evaluator_fingerprint():
                raise ValueError('protected evaluator/data hash changed since session start')
            # Execute the candidate strategy and full stress suite directly to record verified results.
            sys.path.insert(0,str(ROOT/'src'))
            from microarena.engine import Engine
            from microarena.strategy import CandidateStrategy
            from microarena.metrics import summarize
            from microarena.scenarios import SCENARIOS,config_for
            p=ROOT/'outputs'/'candidate'/'summary.json'
            q=ROOT/'outputs'/'candidate_stress'/'stress_results.json'
            r=Engine(ROOT/'data',config_for('base')).run(CandidateStrategy(),p.parent)
            p.write_text(json.dumps(summarize(r),indent=2))
            stressed={}
            for name in SCENARIOS:
                result=Engine(ROOT/'data',config_for(name)).run(CandidateStrategy())
                stressed[name]=summarize(result)
                print('Evaluated scenario:',name)
            q.parent.mkdir(parents=True,exist_ok=True)
            q.write_text(json.dumps(stressed,indent=2))
            append('final_test',summary_sha256=hashfile(p),stress_sha256=hashfile(q),strategy_sha256=hashfile(STRATEGY),code_sha256=code_fingerprint())
        elif a.cmd=='finalize':
            stat,fail=gates()
            report={'status':'PASS' if not fail else 'INCOMPLETE','metrics':stat,'blockers':fail}
            print(json.dumps(report,indent=2))
            if fail:sys.exit(2)
            append('completed',**report)
    except (ValueError,KeyError) as exc:
        print('ERROR:',exc,file=sys.stderr);sys.exit(2)
if __name__=='__main__':main()
