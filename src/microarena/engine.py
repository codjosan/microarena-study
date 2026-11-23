"""Deterministic event simulator: latency-aware quotes, FIFO-ish queue fills, hedge execution,
cash/share PnL, cancel races, venue health and portfolio limits. Research approximation,
not an exchange emulator. No strategy can inspect future ticks via Context.
"""
from collections import defaultdict, deque
from dataclasses import asdict
from pathlib import Path
import csv, json, math
from .types import Quote, Hedge, Order, Fill, Decision, Config
from .data import load_data

class Context:
    __slots__=('tick_id','book','history','inventory','cash','equity','peak_equity',
               'drawdown','live_orders','mark','symbols','venues','recent_fills')
    def __init__(self,t,book,history,inventory,cash,equity,peak,orders,marks,symbols,venues,fills):
        self.tick_id=t
        self.book={k:dict(v) for k,v in book.items()}
        self.history={k:tuple(dict(x) for x in xs) for k,xs in history.items()}
        self.inventory=dict(inventory)
        self.cash=cash;self.equity=equity;self.peak_equity=peak
        self.drawdown=1-equity/peak if peak>0 else 0
        self.live_orders=tuple(dict(x) for x in orders)
        self.mark=dict(marks);self.symbols=tuple(symbols);self.venues=tuple(venues)
        self.recent_fills=tuple(dict(x) for x in fills)

class Engine:
    def __init__(self, data_dir='data', config=None):
        self.manifest,self.raw_books,self.raw_marks=load_data(data_dir)
        self.config=config or Config()
        self.symbols=tuple(self.manifest['symbols'])
        self.venues=tuple(self.manifest['venues'])
        self.tick_sizes={k:float(v[1]) for k,v in self.manifest['symbols'].items()}

    def _stressed_book(self,t):
        c=self.config; out={}
        for key,r in self.raw_books[t].items():
            a=dict(r)
            half=(a['ask']-a['bid'])*(c.stress_spread_multiplier-1)/2
            tick=self.tick_sizes[a['symbol']]
            a['bid']=round(max(tick,a['bid']-half)/tick)*tick
            a['ask']=round((a['ask']+half)/tick)*tick
            a['ask']=max(a['ask'],a['bid']+tick)
            a['bid_depth']=max(1,int(a['bid_depth']*c.stress_depth_multiplier))
            a['ask_depth']=max(1,int(a['ask_depth']*c.stress_depth_multiplier))
            a['market_buy_qty']=max(0,int(a['market_buy_qty']*c.stress_trade_flow_multiplier))
            a['market_sell_qty']=max(0,int(a['market_sell_qty']*c.stress_trade_flow_multiplier))
            a['latency_ticks']=max(1,a['latency_ticks']+c.stress_latency_add)
            if c.stress_venue_offline==a['venue']:a['halted']=1
            out[key]=a
        return out

    def run(self,strategy,out_dir=None):
        c=self.config; symbols=self.symbols; venues=self.venues
        cash=c.initial_cash; inventory={s:0 for s in symbols}
        orders={}; pending_hedges=[]; seq=0; peak=c.initial_cash
        total_fees=0.0; total_notional=0.0; submitted=0; cancel_requests=0
        violations=defaultdict(int); daily=[];fills=[];orders_log=[]
        history=defaultdict(lambda:deque(maxlen=100))
        fills_recent=deque(maxlen=25)
        for t in sorted(self.raw_books):
            book=self._stressed_book(t)
            mark=dict(self.raw_marks[t])
            if c.stress_mark_shock_bps and any(start<=t<start+20 for start in (1000,1450,2050)):
                mark={s:p*(1+c.stress_mark_shock_bps/10000) for s,p in mark.items()}
            # Current snapshot is public for decisions; no future data is exposed.
            for k,r in book.items():history[k].append(r)
            # Activate queued acknowledgements, process cancels after venue latency.
            for oid,o in list(orders.items()):
                if o.cancel_tick is not None and o.cancel_tick<=t:
                    o.status='cancelled';orders_log.append({'tick_id':t,'order_id':oid,'event':'cancel'});del orders[oid]
                    continue
                if o.status=='pending' and o.live_tick<=t:
                    o.status='live';orders_log.append({'tick_id':t,'order_id':oid,'event':'activate'})
            # Execute previously submitted aggressive hedges after their venue latency.
            # Never allow a decision to trade against its own observed snapshot.
            for due,h in list(pending_hedges):
                if due>t:continue
                pending_hedges.remove((due,h))
                r=book[(h.symbol,h.venue)]
                if r['stale'] or r['halted']:
                    violations['blocked_unhealthy_hedge']+=1;continue
                depth=r['ask_depth'] if h.side=='buy' else r['bid_depth']
                capacity=max(0,int(depth*c.max_hedge_participation))
                qty=min(h.qty,capacity)
                if qty<=0:continue
                signed=qty if h.side=='buy' else -qty
                if abs(inventory[h.symbol]+signed)>c.max_inventory_shares:
                    violations['blocked_hedge_risk']+=1;continue
                gross=sum(abs(inventory[s]+(signed if s==h.symbol else 0))*mark[s] for s in symbols)
                if gross>c.max_gross_notional or abs(inventory[h.symbol]+signed)*mark[h.symbol]>c.max_inventory_notional:
                    violations['blocked_hedge_risk']+=1;continue
                impact=c.impact_bps*math.sqrt(qty/max(1,capacity))/10000
                price=(r['ask']*(1+impact) if h.side=='buy' else r['bid']*(1-impact))
                fee=abs(qty*price)*c.taker_fee_bps*c.stress_fee_multiplier/10000
                cash-=signed*price+fee;inventory[h.symbol]+=signed
                total_fees+=fee;total_notional+=abs(qty*price)
                fd=asdict(Fill(t,0,h.symbol,h.venue,h.side,qty,round(price,6),fee,'taker'))
                fills.append(fd);fills_recent.append(fd)
            # Maker matching at this tick occurs BEFORE new decision messages arrive.
            for k in sorted(book):
                r=book[k];sym,venue=k
                if r['halted'] or r['stale']:continue
                for side,flow_field in (('buy','market_sell_qty'),('sell','market_buy_qty')):
                    eligible=[o for o in orders.values() if o.status=='live' and o.quote.symbol==sym and o.quote.venue==venue and o.quote.side==side]
                    # Earlier orders first. Prices must be passive at current best.
                    eligible.sort(key=lambda o:(-o.quote.price if side=='buy' else o.quote.price,o.placed_tick,o.order_id))
                    flow=r[flow_field]
                    if c.stress_toxic_flow_multiplier!=1.0 and t%7==0:
                        flow=int(flow*c.stress_toxic_flow_multiplier)
                    for o in eligible:
                        if flow<=0:break
                        price=o.quote.price
                        if side=='buy' and price>r['bid']+1e-8:continue
                        if side=='sell' and price<r['ask']-1e-8:continue
                        # Orders away from current touch do not fill.
                        if side=='buy' and abs(price-r['bid'])>self.tick_sizes[sym]*0.51:continue
                        if side=='sell' and abs(price-r['ask'])>self.tick_sizes[sym]*0.51:continue
                        consumed=min(o.queue_ahead,flow)
                        o.queue_ahead-=consumed;flow-=consumed
                        if flow<=0:continue
                        qty=min(o.quote.qty-o.executed,int(flow))
                        if qty<=0:continue
                        signed=qty if side=='buy' else -qty
                        hypothetical=inventory[sym]+signed
                        proposed_notional=abs(hypothetical)*mark[sym]
                        proposed_gross=sum(abs(inventory[s])*mark[s] for s in symbols if s!=sym)+proposed_notional
                        if abs(hypothetical)>c.max_inventory_shares or proposed_notional>c.max_inventory_notional or proposed_gross>c.max_gross_notional:
                            violations['blocked_passive_risk']+=1
                            continue
                        flow-=qty;o.executed+=qty
                        fee=abs(qty*price)*(c.maker_fee_bps+(c.stress_fee_multiplier-1)*abs(c.maker_fee_bps))/10000
                        cash-=signed*price+fee;inventory[sym]+=signed
                        total_fees+=fee;total_notional+=abs(qty*price)
                        fill=Fill(t,o.order_id,sym,venue,side,qty,price,fee,'maker')
                        fd=asdict(fill);fills.append(fd);fills_recent.append(fd)
                        if o.executed>=o.quote.qty:
                            o.status='filled';orders_log.append({'tick_id':t,'order_id':o.order_id,'event':'filled'})
                            del orders[o.order_id]
            equity=cash+sum(inventory[s]*mark[s] for s in symbols)
            peak=max(peak,equity);dd=1-equity/peak if peak>0 else 0
            visible_orders=[{'order_id':o.order_id,**asdict(o.quote),'status':o.status,
                             'remaining':o.quote.qty-o.executed,'queue_ahead':round(o.queue_ahead,3)} for o in orders.values()]
            ctx=Context(t,book,history,inventory,cash,equity,peak,visible_orders,mark,symbols,venues,fills_recent)
            try:
                decision=strategy.on_tick(ctx)
                if not isinstance(decision,Decision):raise TypeError('on_tick must return Decision')
            except Exception as exc:
                violations['strategy_exception']+=1
                decision=Decision()
                orders_log.append({'tick_id':t,'order_id':-1,'event':'strategy_exception','detail':repr(exc)})
            # Strict message validation; engine ignores dangerous malformed intents.
            requested={}
            for q in decision.quotes[:c.max_orders_per_tick]:
                if not isinstance(q,Quote) or q.symbol not in symbols or q.venue not in venues or q.side not in ('buy','sell') or not isinstance(q.qty,int) or isinstance(q.qty,bool) or q.qty<=0 or not math.isfinite(q.price) or q.price<=0:
                    violations['invalid_quote']+=1;continue
                key=(q.symbol,q.venue,q.side)
                r=book[(q.symbol,q.venue)]
                tick=self.tick_sizes[q.symbol]
                if abs(q.price/tick-round(q.price/tick))>1e-5 or (q.side=='buy' and q.price>r['bid']+1e-7) or (q.side=='sell' and q.price<r['ask']-1e-7):
                    violations['crossing_or_offtick_quote']+=1;continue
                if q.qty>c.max_inventory_shares or q.qty*q.price>c.max_inventory_notional:
                    violations['oversized_quote']+=1;continue
                requested[key]=q
            if len(decision.quotes)>c.max_orders_per_tick:violations['message_rate']+=1
            # Cancel/reprice old orders; a cancellation does not take immediate effect.
            for oid,o in list(orders.items()):
                key=(o.quote.symbol,o.quote.venue,o.quote.side)
                want=requested.get(key)
                if want!=o.quote and o.cancel_tick is None:
                    r=book[(o.quote.symbol,o.quote.venue)]
                    o.cancel_tick=t+max(1,c.cancel_latency_ticks+c.stress_cancel_delay_add+r['latency_ticks'])
                    cancel_requests+=1;orders_log.append({'tick_id':t,'order_id':oid,'event':'request_cancel'})
            # Reject overlapping reorders until cancellation acknowledgement; not instant queue reset.
            outstanding={(o.quote.symbol,o.quote.venue,o.quote.side) for o in orders.values()}
            for key,q in sorted(requested.items()):
                if key in outstanding:continue
                r=book[(q.symbol,q.venue)]
                if r['stale'] or r['halted']:
                    violations['blocked_unhealthy_quote']+=1;continue
                if dd>=c.max_drawdown:
                    violations['drawdown_quote_kill']+=1;continue
                # Cumulative opening-order reservations guard extreme one-sided outstanding flow.
                reserved=sum((o.quote.qty-o.executed) for o in orders.values() if o.quote.symbol==q.symbol and o.quote.side==q.side)
                if reserved+q.qty>c.max_inventory_shares:
                    violations['blocked_order_reservation']+=1;continue
                seq+=1;submitted+=1
                queue=r['bid_depth'] if q.side=='buy' else r['ask_depth']
                order=Order(seq,q,t,t+max(1,r['latency_ticks']),queue_ahead=max(0.0,queue*.23))
                orders[seq]=order;orders_log.append({'tick_id':t,'order_id':seq,'event':'submit'})
            # Hedge requests are validated now and executed only after venue latency.
            for h in decision.hedges[:c.max_orders_per_tick]:
                if not isinstance(h,Hedge) or h.symbol not in symbols or h.venue not in venues or h.side not in ('buy','sell') or not isinstance(h.qty,int) or isinstance(h.qty,bool) or h.qty<=0:
                    violations['invalid_hedge']+=1;continue
                r=book[(h.symbol,h.venue)]
                if r['stale'] or r['halted']:
                    violations['blocked_unhealthy_hedge']+=1;continue
                if h.qty>c.max_inventory_shares:
                    violations['oversized_hedge']+=1;continue
                pending_hedges.append((t+max(1,r['latency_ticks']),h))
            equity=cash+sum(inventory[s]*mark[s] for s in symbols)
            peak=max(peak,equity);dd=1-equity/peak if peak>0 else 0
            gross=sum(abs(inventory[s])*mark[s] for s in symbols)
            if any(abs(inventory[s])>c.max_inventory_shares or abs(inventory[s])*mark[s]>c.max_inventory_notional+1e-4 for s in symbols) or gross>c.max_gross_notional+1e-4:
                violations['post_trade_limit']+=1
            split='train' if t<=self.manifest['train_end'] else ('validation' if t<=self.manifest['validation_end'] else 'test')
            daily.append({'tick_id':t,'split':split,'cash':cash,'equity':equity,'gross_notional':gross,
                          'drawdown':dd,'inventory':dict(inventory),'outstanding_orders':len(orders),
                          'total_fee':total_fees,'trade_notional':total_notional,'submitted':submitted})
        # Liquidate residual inventory at final executable marks; include terminal liquidation expense.
        terminal_cost=0.0
        for s,qty in inventory.items():
            if qty:
                p=self.raw_marks[max(self.raw_marks)][s]
                terminal_cost+=abs(qty*p)*c.taker_fee_bps*c.stress_fee_multiplier/10000
        terminal_equity=daily[-1]['equity']-terminal_cost
        result={'daily':daily,'fills':fills,'orders':orders_log,'violations':dict(violations),
                'terminal_equity':terminal_equity,'terminal_liquidation_cost':terminal_cost,
                'total_fees':total_fees,'submitted':submitted,'cancellations':cancel_requests,
                'filled_shares':sum(f['qty'] for f in fills)}
        if out_dir:
            p=Path(out_dir);p.mkdir(parents=True,exist_ok=True)
            def export(name,rows):
                fields=sorted(set().union(*(r.keys() for r in rows))) if rows else ['tick_id']
                with (p/name).open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
                    for row in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,dict) else v for k,v in row.items()})
            export('equity.csv',daily);export('fills.csv',fills);export('orders.csv',orders_log)
            (p/'violations.json').write_text(json.dumps(dict(violations),indent=2))
        return result
