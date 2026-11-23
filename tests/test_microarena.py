import unittest,sys,tempfile,json,math,csv,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from microarena.types import Config,Quote,Hedge,Decision,Order,Fill
from microarena.engine import Engine
from microarena.data import load_data
from microarena.baseline import NaiveSymmetricMaker
from microarena.strategy import CandidateStrategy
from microarena.metrics import summarize
from microarena.scenarios import SCENARIOS,config_for
from fixture_factory import generate

class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        generate(cls.tmp.name,seed=87,n=65)
        cls.manifest,cls.book,cls.marks=load_data(cls.tmp.name)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_row_count(self):self.assertEqual(sum(map(len,self.book.values())),390)
    def test_mark_panel(self):self.assertEqual(len(self.marks),65)
    def test_symbols(self):self.assertEqual(set(self.manifest['symbols']),{'ALPHA','BETA','GAMMA'})
    def test_venues(self):self.assertEqual(self.manifest['venues'],['NORTH','SOUTH'])
    def test_bid_ask_ordered(self):self.assertTrue(all(r['bid']<r['ask'] for b in self.book.values() for r in b.values()))
    def test_prices_positive(self):self.assertTrue(all(r['bid']>0 for b in self.book.values() for r in b.values()))
    def test_depth_positive(self):self.assertTrue(all(r['bid_depth']>0 and r['ask_depth']>0 for b in self.book.values() for r in b.values()))
    def test_latency_positive(self):self.assertTrue(all(r['latency_ticks']>=1 for b in self.book.values() for r in b.values()))
    def test_repeatability(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(tmp,seed=87,n=65)
            self.assertEqual(Path(tmp,'market_stream.csv').read_bytes(),Path(self.tmp.name,'market_stream.csv').read_bytes())
    def test_seed_changes_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(tmp,seed=88,n=65)
            self.assertNotEqual(Path(tmp,'market_stream.csv').read_bytes(),Path(self.tmp.name,'market_stream.csv').read_bytes())
    def test_no_hidden_regime_labels(self):
        row=self.book[0][('ALPHA','NORTH')]
        self.assertNotIn('regime',row)
        self.assertNotIn('split',row)
    def test_marks_positive(self):self.assertTrue(all(v>0 for mark in self.marks.values() for v in mark.values()))
    def test_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(tmp,seed=87,n=6)
            p=Path(tmp)/'market_stream.csv'
            rows=p.read_text().splitlines();p.write_text('\n'.join(rows+[rows[1]])+'\n')
            with self.assertRaises(ValueError):load_data(tmp)
    def test_incomplete_panel_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(tmp,seed=87,n=6)
            p=Path(tmp)/'market_stream.csv'
            rows=p.read_text().splitlines();p.write_text('\n'.join(rows[:-1])+'\n')
            with self.assertRaises(ValueError):load_data(tmp)
    def test_invalid_market_row_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(tmp,seed=87,n=6)
            p=Path(tmp)/'market_stream.csv'
            s=p.read_text();s=s.replace('100.', '-100.',1);p.write_text(s)
            with self.assertRaises(ValueError):load_data(tmp)

class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=DataTests.tmp.name if hasattr(DataTests,'tmp') else str(ROOT/'data')
        # This class works even when run independently.
        cls.tmp=tempfile.TemporaryDirectory();generate(cls.tmp.name,seed=91,n=90)
        cls.folder=cls.tmp.name
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def engine(self,policy,cfg=None):return Engine(self.folder,cfg).run(policy)
    def test_flat_returns_initial_equity(self):
        r=self.engine(CandidateStrategy());self.assertAlmostEqual(r['terminal_equity'],1_000_000,places=6)
    def test_flat_has_no_orders(self):self.assertEqual(self.engine(CandidateStrategy())['submitted'],0)
    def test_flat_has_no_fills(self):self.assertEqual(len(self.engine(CandidateStrategy())['fills']),0)
    def test_baseline_makes_orders(self):self.assertGreater(self.engine(NaiveSymmetricMaker())['submitted'],0)
    def test_all_inventory_integers(self):
        r=self.engine(NaiveSymmetricMaker())
        self.assertTrue(all(all(isinstance(v,int) for v in row['inventory'].values()) for row in r['daily']))
    def test_no_future_context(self):
        class Check:
            def on_tick(self,ctx):
                assert all(row['tick_id']<=ctx.tick_id for hist in ctx.history.values() for row in hist)
                assert all(row['tick_id']==ctx.tick_id for row in ctx.book.values())
                assert not hasattr(ctx,'split')
                return Decision()
        self.assertNotIn('strategy_exception',self.engine(Check())['violations'])
    def test_no_same_tick_maker_fill(self):
        class Fixed:
            def on_tick(self,ctx):
                q=ctx.book[('ALPHA','NORTH')]
                return Decision(quotes=[Quote('ALPHA','NORTH','buy',q['bid'],20)])
        r=self.engine(Fixed())
        submit={o['order_id']:o['tick_id'] for o in r['orders'] if o['event']=='submit'}
        self.assertTrue(all(f['tick_id']>submit[f['order_id']] for f in r['fills'] if f['liquidity']=='maker'))
    def test_no_same_tick_hedge_fill(self):
        class H:
            def on_tick(self,ctx):
                return Decision(hedges=[Hedge('ALPHA','NORTH','buy',1)] if ctx.tick_id==0 else [])
        r=self.engine(H())
        self.assertTrue(all(f['tick_id']>0 for f in r['fills']))
    def test_invalid_quote_is_rejected(self):
        class Bad:
            def on_tick(self,ctx):return Decision(quotes=[Quote('INVALID','NORTH','buy',10,3)])
        self.assertGreater(self.engine(Bad())['violations'].get('invalid_quote',0),0)
    def test_zero_qty_quote_rejected(self):
        class Bad:
            def on_tick(self,ctx):return Decision(quotes=[Quote('ALPHA','NORTH','buy',1,0)])
        self.assertGreater(self.engine(Bad())['violations'].get('invalid_quote',0),0)
    def test_nan_quote_rejected(self):
        class Bad:
            def on_tick(self,ctx):return Decision(quotes=[Quote('ALPHA','NORTH','buy',float('nan'),3)])
        self.assertGreater(self.engine(Bad())['violations'].get('invalid_quote',0),0)
    def test_crossed_quote_rejected(self):
        class Bad:
            def on_tick(self,ctx):
                p=ctx.book[('ALPHA','NORTH')]['ask'];return Decision(quotes=[Quote('ALPHA','NORTH','buy',p,3)])
        self.assertGreater(self.engine(Bad())['violations'].get('crossing_or_offtick_quote',0),0)
    def test_giant_quote_rejected(self):
        class Bad:
            def on_tick(self,ctx):
                p=ctx.book[('ALPHA','NORTH')]['bid'];return Decision(quotes=[Quote('ALPHA','NORTH','buy',p,3000)])
        self.assertGreater(self.engine(Bad())['violations'].get('oversized_quote',0),0)
    def test_bad_hedge_rejected(self):
        class Bad:
            def on_tick(self,ctx):return Decision(hedges=[Hedge('ALPHA','NORTH','sell',-10)])
        self.assertGreater(self.engine(Bad())['violations'].get('invalid_hedge',0),0)
    def test_bad_strategy_return_caught(self):
        class Bad:
            def on_tick(self,ctx):return []
        self.assertEqual(self.engine(Bad())['violations']['strategy_exception'],90)
    def test_bad_strategy_exception_caught(self):
        class Bad:
            def on_tick(self,ctx):raise RuntimeError('simulated error')
        self.assertEqual(self.engine(Bad())['violations']['strategy_exception'],90)
    def test_no_post_trade_limits_baseline(self):
        self.assertEqual(self.engine(NaiveSymmetricMaker())['violations'].get('post_trade_limit',0),0)
    def test_portfolio_inventory_bounds(self):
        r=self.engine(NaiveSymmetricMaker())
        self.assertTrue(all(abs(v)<=300 for row in r['daily'] for v in row['inventory'].values()))
    def test_portfolio_gross_bounds(self):
        r=self.engine(NaiveSymmetricMaker())
        self.assertTrue(all(row['gross_notional']<=240000+1e-6 for row in r['daily']))
    def test_terminal_valuation(self):
        r=self.engine(NaiveSymmetricMaker());self.assertAlmostEqual(r['terminal_equity'],r['daily'][-1]['equity']-r['terminal_liquidation_cost'],places=6)
    def test_deterministic_result(self):
        a=self.engine(NaiveSymmetricMaker());b=self.engine(NaiveSymmetricMaker())
        self.assertEqual(a['fills'],b['fills']);self.assertEqual(a['daily'],b['daily'])
    def test_spread_stress_increases_spread(self):
        eng=Engine(self.folder,config_for('spread_3x'))
        a=eng.raw_books[0][('ALPHA','NORTH')];b=eng._stressed_book(0)[('ALPHA','NORTH')]
        self.assertGreaterEqual(b['ask']-b['bid'],a['ask']-a['bid']-1e-6)
    def test_venue_outage_stops_quotes(self):
        eng=Engine(self.folder,config_for('north_down'))
        self.assertTrue(all(row['halted'] for tick in eng.raw_books for key,row in eng._stressed_book(tick).items() if key[1]=='NORTH'))
    def test_depth_stress_lower_depth(self):
        eng=Engine(self.folder,config_for('depth_20pct'))
        self.assertLessEqual(eng._stressed_book(0)[('ALPHA','NORTH')]['bid_depth'],eng.raw_books[0][('ALPHA','NORTH')]['bid_depth'])
    def test_latency_stress_adds_five(self):
        eng=Engine(self.folder,config_for('latency_plus_5'))
        self.assertEqual(eng._stressed_book(0)[('ALPHA','NORTH')]['latency_ticks'],eng.raw_books[0][('ALPHA','NORTH')]['latency_ticks']+5)
    def test_metric_splits_present(self):
        # Mini fixture uses train split only, so only train/all metrics are expected.
        summary=summarize(self.engine(NaiveSymmetricMaker()))
        self.assertIn('train',summary);self.assertIn('all',summary)
    def test_metric_filled_shares(self):
        r=self.engine(NaiveSymmetricMaker());m=summarize(r)
        self.assertEqual(m['filled_shares'],sum(f['qty'] for f in r['fills']))
    def test_metric_fees_finite(self):self.assertTrue(math.isfinite(summarize(self.engine(NaiveSymmetricMaker()))['total_fees']))
    def test_hedge_fills_have_taker_fee(self):
        class H:
            def on_tick(self,ctx):return Decision(hedges=[Hedge('ALPHA','NORTH','buy',1)] if ctx.tick_id==0 else [])
        r=self.engine(H())
        self.assertTrue(any(f['liquidity']=='taker' and f['fee']>0 for f in r['fills']))
    def test_no_instant_cancel_ack(self):
        class Flip:
            def on_tick(self,ctx):
                if ctx.tick_id==0:
                    p=ctx.book[('ALPHA','NORTH')]['bid'];return Decision(quotes=[Quote('ALPHA','NORTH','buy',p,20)])
                return Decision()
        r=self.engine(Flip())
        sub=[x for x in r['orders'] if x['event']=='submit']
        cancel=[x for x in r['orders'] if x['event']=='cancel']
        self.assertTrue(sub and cancel)
        self.assertGreater(cancel[0]['tick_id'],sub[0]['tick_id']+1)
    def test_no_quote_fills_on_stale_or_halt(self):
        r=self.engine(NaiveSymmetricMaker());data=Engine(self.folder)
        for f in r['fills']:
            row=data.raw_books[f['tick_id']][(f['symbol'],f['venue'])]
            self.assertFalse(row['stale'] or row['halted'])

class ScenarioTests(unittest.TestCase):
    def test_count(self):self.assertEqual(len(SCENARIOS),15)
    def test_names_unique(self):self.assertEqual(len(SCENARIOS),len(set(SCENARIOS)))
    def test_default_config_unchanged(self):
        c=Config();config_for('fees_3x',c);self.assertEqual(c.stress_fee_multiplier,1)
    def test_unknown_case(self):
        with self.assertRaises(KeyError):config_for('UNKNOWN')
    def test_fee_multiplier(self):self.assertEqual(config_for('fees_3x').stress_fee_multiplier,3)
    def test_crisis_liquidity(self):self.assertEqual(config_for('combined_crisis').stress_depth_multiplier,0.2)
    def test_mark_gap_direction(self):self.assertLess(config_for('mark_gap_minus_300bps').stress_mark_shock_bps,0)
    def test_outage_target(self):self.assertEqual(config_for('north_down').stress_venue_offline,'NORTH')

class LedgerTests(unittest.TestCase):
    def test_empty_chain(self):
        import study
        self.assertTrue(study.check_chain([]))
    def test_tampered_chain(self):
        import study
        core={'seq':0,'at':'2026-11-23T00:00:00+00:00','kind':'start','prev':'0'*64,'data':{}}
        entry={**core,'digest':hashlib.sha256(study.event_canonical(core).encode()).hexdigest()}
        self.assertTrue(study.check_chain([entry]))
        with self.assertRaises(ValueError):study.check_chain([{**entry,'data':{'hack':True}}])
    def test_chain_prev_detected(self):
        import study
        with self.assertRaises(ValueError):study.check_chain([{'seq':0,'prev':'wrong','digest':'x'}])
    def test_stage_count(self):
        import study
        self.assertEqual(len(study.STAGES),8)
    def test_prompt_count(self):
        import study
        self.assertGreaterEqual(len(study.PROMPTS),30)
    def test_schedule_ends_at_hour_seven(self):
        import study
        self.assertEqual(int(study.STAGES[-1][0])-1,7)

if __name__=='__main__':unittest.main()
