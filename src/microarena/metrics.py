import math

def summarize(result,starting_cash=1_000_000.0):
    daily=result['daily'];out={}
    for split in ('train','validation','test','all'):
        rows=daily if split=='all' else [r for r in daily if r['split']==split]
        if not rows:continue
        first=daily.index(rows[0]);start=starting_cash if first==0 else daily[first-1]['equity']
        returns=[];prev=start;peak=start;dd=0.0
        for r in rows:
            returns.append(r['equity']/prev-1 if prev else 0);prev=r['equity']
            peak=max(peak,r['equity']);dd=max(dd,1-r['equity']/peak)
        ending=rows[-1]['equity']-(result['terminal_liquidation_cost'] if split in ('test','all') else 0)
        mu=sum(returns)/len(returns)
        sd=math.sqrt(sum((x-mu)**2 for x in returns)/max(1,len(returns)-1))
        out[split]={'ticks':len(rows),'net_return_pct':round(100*(ending/start-1),5),
                    'max_drawdown_pct':round(100*dd,5),'sharpe_per_tick':round(mu/sd,5) if sd else 0.0,
                    'end_equity':round(ending,2),'avg_gross_notional':round(sum(r['gross_notional'] for r in rows)/len(rows),2)}
    out['maker_fills']=sum(1 for x in result['fills'] if x['liquidity']=='maker')
    out['taker_fills']=sum(1 for x in result['fills'] if x['liquidity']=='taker')
    out['filled_shares']=result['filled_shares'];out['submitted']=result['submitted']
    out['cancellations']=result['cancellations'];out['total_fees']=round(result['total_fees'],2)
    out['terminal_liquidation_cost']=round(result['terminal_liquidation_cost'],2)
    out['violations']=result['violations']
    return out
