import math, unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from microarena.research import *
class ResearchTests(unittest.TestCase):
    def test_ewma_length(self):self.assertEqual(len(ewma([1,2,3])),3)
    def test_ewma_first(self):self.assertEqual(ewma([1,2,3])[0],1)
    def test_ewma_smoothing(self):self.assertGreater(ewma([0,1,1])[-1],0)
    def test_invalid_decay(self):
        with self.assertRaises(ValueError):ewma([1],1)
    def test_rolling_vol(self):self.assertGreater(rolling_vol([1,-1,1])[2],0)
    def test_invalid_rolling(self):
        with self.assertRaises(ValueError):rolling_vol([1],1)
    def test_imbalance_zero(self):self.assertEqual(imbalance_signal({'bid_depth':0,'ask_depth':0}),0)
    def test_imbalance_positive(self):self.assertGreater(imbalance_signal({'bid_depth':80,'ask_depth':20}),0)
    def test_flow_imbalance(self):self.assertGreater(order_flow_imbalance([{'market_buy_qty':20,'market_sell_qty':5}]),0)
    def test_queue_fills(self):self.assertEqual(queue_fill_estimate(10,20,15),5)
    def test_queue_doesnt_fill(self):self.assertEqual(queue_fill_estimate(100,20,15),0)
    def test_queue_input_rejected(self):
        with self.assertRaises(ValueError):queue_fill_estimate(-1,20,15)
    def test_pnl_reconcile(self):self.assertTrue(pnl_reconcile(100,{'A':2},{'A':10},120)['passed'])
    def test_pnl_reconcile_failure(self):self.assertFalse(pnl_reconcile(100,{'A':2},{'A':10},125)['passed'])
    def test_inventory_var_nonnegative(self):self.assertGreater(inventory_var({'A':5},{'A':10},{'A':.02}),0)
    def test_bootstrap_reproducible(self):
        self.assertEqual(block_bootstrap_mean([0,1,2]*20,replicates=20),block_bootstrap_mean([0,1,2]*20,replicates=20))
    def test_bootstrap_flat(self):self.assertEqual(block_bootstrap_mean([1]*20,replicates=20)['lower_95'],1)
    def test_bootstrap_bad(self):
        with self.assertRaises(ValueError):block_bootstrap_mean([],replicates=20)
    def test_activity(self):self.assertEqual(quote_activity([],[])['filled_shares'],0)
    def test_venue_aggregation(self):
        f=[{'venue':'X','qty':5,'fee':1,'price':10}]
        self.assertEqual(by_venue(f)['X']['notional'],50)
