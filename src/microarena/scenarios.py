from dataclasses import replace
from .types import Config

SCENARIOS={
    'base':{},
    'fees_3x':{'stress_fee_multiplier':3},
    'spread_3x':{'stress_spread_multiplier':3},
    'depth_20pct':{'stress_depth_multiplier':0.2},
    'latency_plus_5':{'stress_latency_add':5},
    'cancel_delay_plus_8':{'stress_cancel_delay_add':8},
    'north_down':{'stress_venue_offline':'NORTH'},
    'south_down':{'stress_venue_offline':'SOUTH'},
    'flow_30pct':{'stress_trade_flow_multiplier':0.3},
    'flow_250pct':{'stress_trade_flow_multiplier':2.5},
    'toxic_flow_4x':{'stress_toxic_flow_multiplier':4},
    'mark_gap_minus_300bps':{'stress_mark_shock_bps':-300},
    'mark_gap_plus_300bps':{'stress_mark_shock_bps':300},
    'combined_crisis':{'stress_fee_multiplier':2,'stress_spread_multiplier':3,'stress_depth_multiplier':0.2,
                       'stress_latency_add':5,'stress_cancel_delay_add':5},
    'combined_toxic':{'stress_toxic_flow_multiplier':5,'stress_trade_flow_multiplier':1.8,'stress_latency_add':3}
}

def config_for(name,base=None):
    if name not in SCENARIOS:raise KeyError(name)
    return replace(base or Config(),**SCENARIOS[name])
