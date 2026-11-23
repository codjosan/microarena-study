from pathlib import Path
import sys,collections,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from microarena.data import load_data
m,books,marks=load_data(ROOT/'data')
expected=json.loads((ROOT/'data'/'DATA_HASHES.json').read_text())
for name,digest in expected.items():
    actual=hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest()
    assert actual==digest, f'fingerprint mismatch: {name}'
stale=sum(r['stale'] for b in books.values() for r in b.values())
halted=sum(r['halted'] for b in books.values() for r in b.values())
assert len(books)==2400
assert sum(len(b) for b in books.values())==14400
assert len(marks)==2400
assert all(set(mark)==set(m['symbols']) for mark in marks.values())
assert all(row['bid']<row['ask'] for b in books.values() for row in b.values())
print(json.dumps({'ticks':len(books),'market_rows':sum(len(b) for b in books.values()),
                  'halts':halted,'stale':stale,'status':'PASS'},indent=2))
