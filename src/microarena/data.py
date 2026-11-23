from collections import defaultdict
from pathlib import Path
import csv, json, math

NUM=('bid','ask','imbalance')
INT=('tick_id','bid_depth','ask_depth','market_buy_qty','market_sell_qty','latency_ticks','stale','halted')

def load_data(folder):
    folder=Path(folder)
    manifest=json.loads((folder/'manifest.json').read_text())
    book=defaultdict(dict)
    with (folder/'market_stream.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            for k in NUM:row[k]=float(row[k])
            for k in INT:row[k]=int(row[k])
            if not math.isfinite(row['bid']) or not math.isfinite(row['ask']) or row['bid']<=0 or row['ask']<=row['bid']:
                raise ValueError('invalid market row')
            key=(row['symbol'],row['venue'])
            if key in book[row['tick_id']]:raise ValueError('duplicate market key')
            book[row['tick_id']][key]=row
    marks=defaultdict(dict)
    with (folder/'reference_marks.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            marks[int(row['tick_id'])][row['symbol']]=float(row['reference_mid'])
    if set(book)!=set(marks):raise ValueError('mark times mismatch')
    if len(book)!=manifest['ticks']:raise ValueError('tick count mismatch')
    if any(len(book[t])!=len(manifest['venues'])*len(manifest['symbols']) for t in book):
        raise ValueError('market panel incomplete')
    return manifest,book,marks
