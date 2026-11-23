from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class Quote:
    symbol: str
    venue: str
    side: str                 # buy or sell
    price: float
    qty: int

@dataclass(frozen=True)
class Hedge:
    symbol: str
    venue: str
    side: str
    qty: int

@dataclass
class Decision:
    quotes: list[Quote] = field(default_factory=list)
    hedges: list[Hedge] = field(default_factory=list)

@dataclass
class Order:
    order_id: int
    quote: Quote
    placed_tick: int
    live_tick: int
    queue_ahead: float
    cancel_tick: Optional[int] = None
    executed: int = 0
    status: str = 'pending'

@dataclass
class Fill:
    tick_id: int
    order_id: int
    symbol: str
    venue: str
    side: str
    qty: int
    price: float
    fee: float
    liquidity: str

@dataclass
class Config:
    initial_cash: float = 1_000_000.0
    max_inventory_shares: int = 300
    max_inventory_notional: float = 120_000.0
    max_gross_notional: float = 240_000.0
    max_drawdown: float = 0.06
    max_orders_per_tick: int = 30
    maker_fee_bps: float = -0.5
    taker_fee_bps: float = 6.0
    impact_bps: float = 4.0
    cancel_latency_ticks: int = 1
    order_to_trade_limit: int = 150
    max_hedge_participation: float = 0.3
    stress_spread_multiplier: float = 1.0
    stress_depth_multiplier: float = 1.0
    stress_latency_add: int = 0
    stress_fee_multiplier: float = 1.0
    stress_trade_flow_multiplier: float = 1.0
    stress_venue_offline: str = ''
    stress_mark_shock_bps: float = 0.0
    stress_cancel_delay_add: int = 0
    stress_toxic_flow_multiplier: float = 1.0
