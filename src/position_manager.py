"""
💰 Advanced Position Management - Multi-TP + Trailing Stop
===========================================================
Strategy:
- TP1: Close 50% at +2 ATR → Move SL to breakeven
- TP2: Close 30% at +3 ATR → Activate trailing stop
- Runner: 20% rides with 1.5 ATR trailing stop

Handles:
- Partial take profits
- Dynamic trailing stops  
- Break-even management after TP1
- Max drawdown protection
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class TakeProfitLevel:
    price: float
    size_pct: float  # Percentage of position to close
    triggered: bool = False
    name: str = ""  # TP1, TP2, etc.


@dataclass
class ManagedPosition:
    symbol: str
    side: str
    entry_price: float
    current_size: float
    original_size: float
    leverage: int
    stop_loss: float
    original_stop_loss: float  # Keep track for reference
    trailing_active: bool
    trailing_stop: Optional[float]
    trailing_atr: float  # ATR value for trailing distance
    take_profits: List[TakeProfitLevel]
    highest_price: float  # For trailing (long)
    lowest_price: float   # For trailing (short)
    opened_at: datetime
    pnl_realized: float
    breakeven_moved: bool = False  # Track if we moved to BE


class PositionManager:
    """
    Advanced position management with multi-TP and trailing stop.
    
    Strategy Flow:
    1. Entry → SL set at 2 ATR
    2. Price hits TP1 (+2 ATR) → Close 50%, move SL to breakeven
    3. Price hits TP2 (+3 ATR) → Close 30%, activate trailing (1.5 ATR)
    4. Trailing stop manages remaining 20% until exit
    """
    
    def __init__(self, config, client):
        self.config = config
        self.client = client
        self.logger = logging.getLogger(__name__)
        self.managed_positions: Dict[str, ManagedPosition] = {}
        self.pending_orders: Dict[str, datetime] = {}  # Track pending orders to prevent duplicates
        self.ORDER_COOLDOWN_SECONDS = 10  # Minimum time between orders for same symbol
    
    def create_managed_position(self, symbol: str, side: str, entry_price: float,
                                size: float, leverage: int, atr: float,
                                tp1_price: float = None, tp2_price: float = None,
                                sl_price: float = None) -> ManagedPosition:
        """
        Create a new managed position with multi-TP levels.
        
        TP Structure:
        - TP1 → Close 50%
        - TP2 → Close 30%
        - Runner: 20% with trailing stop
        
        Supports both:
        - Pre-calculated TP/SL prices (percentage mode)
        - ATR-based calculation (ATR mode fallback)
        """
        
        tp_levels = []
        
        if side == "Buy":
            # Use provided prices or fallback to ATR calculation
            tp1 = tp1_price if tp1_price else entry_price + (atr * 2.0)
            tp2 = tp2_price if tp2_price else entry_price + (atr * 3.0)
            stop_loss = sl_price if sl_price else entry_price - (atr * 2.0)
            
            tp_levels.append(TakeProfitLevel(
                price=tp1,
                size_pct=0.50,
                name="TP1"
            ))
            tp_levels.append(TakeProfitLevel(
                price=tp2,
                size_pct=0.30,
                name="TP2"
            ))
        else:
            # Short positions - inverted
            tp1 = tp1_price if tp1_price else entry_price - (atr * 2.0)
            tp2 = tp2_price if tp2_price else entry_price - (atr * 3.0)
            stop_loss = sl_price if sl_price else entry_price + (atr * 2.0)
            
            tp_levels.append(TakeProfitLevel(
                price=tp1,
                size_pct=0.50,
                name="TP1"
            ))
            tp_levels.append(TakeProfitLevel(
                price=tp2,
                size_pct=0.30,
                name="TP2"
            ))
        
        position = ManagedPosition(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            current_size=size,
            original_size=size,
            leverage=leverage,
            stop_loss=stop_loss,
            original_stop_loss=stop_loss,
            trailing_active=False,
            trailing_stop=None,
            trailing_atr=atr * 1.5,  # 1.5 ATR trailing distance
            take_profits=tp_levels,
            highest_price=entry_price,
            lowest_price=entry_price,
            opened_at=datetime.now(),
            pnl_realized=0,
            breakeven_moved=False
        )
        
        self.managed_positions[symbol] = position
        
        self.logger.info(f"📊 Position Created: {symbol} {side}")
        self.logger.info(f"   Entry: ${entry_price:.4f} | SL: ${stop_loss:.4f}")
        self.logger.info(f"   TP1 (+2 ATR): ${tp_levels[0].price:.4f} → Close 50%")
        self.logger.info(f"   TP2 (+3 ATR): ${tp_levels[1].price:.4f} → Close 30%")
        self.logger.info(f"   Runner: 20% with {atr * 1.5:.4f} trailing stop")
        
        return position
    
    def update_position(self, symbol: str, current_price: float) -> List[Dict]:
        """
        Update position and check for TP/trailing actions.
        
        Flow:
        1. Check if TP1 hit → Close 50%, move SL to breakeven
        2. Check if TP2 hit → Close 30%, activate trailing for 20% runner
        3. If trailing active → Update trailing stop, check for exit
        """
        
        if symbol not in self.managed_positions:
            return []
        
        position = self.managed_positions[symbol]
        actions = []
        
        # Update price extremes (for trailing calculation)
        if current_price > position.highest_price:
            position.highest_price = current_price
        if current_price < position.lowest_price:
            position.lowest_price = current_price
        
        # === CHECK TAKE PROFIT LEVELS ===
        for tp in position.take_profits:
            if tp.triggered:
                continue
            
            # Check if TP level hit
            hit_tp = (position.side == "Buy" and current_price >= tp.price) or \
                     (position.side == "Sell" and current_price <= tp.price)
            
            if hit_tp:
                tp.triggered = True
                close_size = round(position.original_size * tp.size_pct, 3)
                
                actions.append({
                    "action": "partial_close",
                    "symbol": symbol,
                    "size": close_size,
                    "reason": f"🎯 {tp.name} hit at ${tp.price:.4f} - closing {tp.size_pct:.0%}"
                })
                
                # TP1 HIT → Move SL to breakeven (risk-free trade!)
                if tp.name == "TP1" and not position.breakeven_moved:
                    position.breakeven_moved = True
                    actions.append({
                        "action": "move_stop",
                        "symbol": symbol,
                        "new_stop": position.entry_price,
                        "reason": "🔒 Moving SL to breakeven (risk-free!)"
                    })
                    position.stop_loss = position.entry_price
                
                # TP2 HIT → Activate trailing stop for the 20% runner
                if tp.name == "TP2" and not position.trailing_active:
                    position.trailing_active = True
                    # Initialize trailing stop at current level
                    position.trailing_stop = self._calculate_trailing_stop(position, current_price)
                    self.logger.info(f"🚀 Trailing stop ACTIVATED for {symbol} runner (20%)")
                    self.logger.info(f"   Trailing distance: {position.trailing_atr:.4f}")
                    self.logger.info(f"   Initial trailing stop: ${position.trailing_stop:.4f}")
        
        # === MANAGE TRAILING STOP (for 20% runner) ===
        if position.trailing_active and position.current_size > 0:
            new_trailing = self._calculate_trailing_stop(position, current_price)
            
            # Only move trailing in profit direction (ratchet up/down)
            if position.side == "Buy":
                if new_trailing > position.trailing_stop:
                    old_ts = position.trailing_stop
                    position.trailing_stop = new_trailing
                    self.logger.info(f"📈 Trailing stop raised: ${old_ts:.4f} → ${new_trailing:.4f}")
            else:  # Sell/Short
                if new_trailing < position.trailing_stop:
                    old_ts = position.trailing_stop
                    position.trailing_stop = new_trailing
                    self.logger.info(f"📉 Trailing stop lowered: ${old_ts:.4f} → ${new_trailing:.4f}")
            
            # Check if trailing stop hit → Close runner
            trailing_hit = (position.side == "Buy" and current_price <= position.trailing_stop) or \
                          (position.side == "Sell" and current_price >= position.trailing_stop)
            
            if trailing_hit:
                actions.append({
                    "action": "close_all",
                    "symbol": symbol,
                    "size": position.current_size,
                    "reason": f"🏁 Trailing stop hit at ${position.trailing_stop:.4f} - closing runner"
                })
        
        # === CHECK HARD STOP LOSS (before TP1) ===
        if not position.trailing_active and position.current_size > 0:
            sl_hit = (position.side == "Buy" and current_price <= position.stop_loss) or \
                     (position.side == "Sell" and current_price >= position.stop_loss)
            
            if sl_hit:
                actions.append({
                    "action": "close_all",
                    "symbol": symbol,
                    "size": position.current_size,
                    "reason": f"❌ Stop loss hit at ${position.stop_loss:.4f}"
                })
        
        return actions
    
    def _calculate_trailing_stop(self, position: ManagedPosition, 
                                  current_price: float) -> float:
        """
        Calculate trailing stop using ATR-based distance.
        
        Uses 1.5 ATR trailing distance (stored in position.trailing_atr).
        This adapts to the coin's volatility.
        """
        
        if position.side == "Buy":
            # Long: trail below highest price
            return position.highest_price - position.trailing_atr
        else:
            # Short: trail above lowest price
            return position.lowest_price + position.trailing_atr
    
    def _get_break_even_distance(self, position: ManagedPosition, 
                                  current_price: float) -> float:
        """Get distance from entry as percentage."""
        
        if position.side == "Buy":
            return (current_price - position.entry_price) / position.entry_price
        else:
            return (position.entry_price - current_price) / position.entry_price
    
    def execute_actions(self, actions: List[Dict]) -> None:
        """Execute position management actions."""
        
        for action in actions:
            try:
                symbol = action.get("symbol", "")
                
                # Check cooldown for order actions to prevent duplicate orders
                if action["action"] in ["partial_close", "close_all"]:
                    if symbol in self.pending_orders:
                        time_since = (datetime.now() - self.pending_orders[symbol]).total_seconds()
                        if time_since < self.ORDER_COOLDOWN_SECONDS:
                            self.logger.warning(f"⏳ Skipping duplicate order for {symbol} (cooldown: {self.ORDER_COOLDOWN_SECONDS - time_since:.1f}s remaining)")
                            continue
                    # Mark order as pending
                    self.pending_orders[symbol] = datetime.now()
                
                if action["action"] == "partial_close":
                    self._partial_close(action)
                elif action["action"] == "close_all":
                    self._close_position(action)
                elif action["action"] == "move_stop":
                    self._move_stop(action)
            except Exception as e:
                self.logger.error(f"Failed to execute action {action}: {e}")
    
    def _partial_close(self, action: Dict) -> None:
        """Close part of a position."""
        symbol = action["symbol"]
        size = action["size"]
        
        position = self.managed_positions.get(symbol)
        if not position:
            return
        
        # Skip if position is already closed (size <= 0)
        if position.current_size <= 0:
            self.logger.warning(f"⚠️ {symbol} already closed, removing from managed positions")
            if symbol in self.managed_positions:
                del self.managed_positions[symbol]
            return
        
        # Fix floating point precision - round to proper decimal places
        qty_precision = {"XRPUSDT": 1, "AVAXUSDT": 1, "LINKUSDT": 1, "DOGEUSDT": 0, "BNBUSDT": 2}.get(symbol, 2)
        size = round(size, qty_precision)
        
        close_side = "Sell" if position.side == "Buy" else "Buy"
        
        order_id = self.client.place_order(
            symbol=symbol,
            side=close_side,
            qty=size,
            reduce_only=True
        )
        
        if order_id:
            position.current_size -= size
            self.logger.info(f"✅ Partial close: {symbol} {size} - {action['reason']}")
        else:
            # Order failed - might be already closed, sync state
            self.logger.warning(f"⚠️ Partial close failed for {symbol}, syncing state")
            if symbol in self.managed_positions:
                del self.managed_positions[symbol]
    
    def _close_position(self, action: Dict) -> None:
        """Close entire position."""
        symbol = action["symbol"]
        
        position = self.managed_positions.get(symbol)
        if not position:
            return
        
        # Skip if position is already closed
        if position.current_size <= 0:
            self.logger.warning(f"⚠️ {symbol} already closed, removing from managed positions")
            del self.managed_positions[symbol]
            return
        
        # Fix floating point precision
        qty_precision = {"XRPUSDT": 1, "AVAXUSDT": 1, "LINKUSDT": 1, "DOGEUSDT": 0, "BNBUSDT": 2}.get(symbol, 2)
        close_qty = round(position.current_size, qty_precision)
        
        close_side = "Sell" if position.side == "Buy" else "Buy"
        
        order_id = self.client.place_order(
            symbol=symbol,
            side=close_side,
            qty=close_qty,
            reduce_only=True
        )
        
        if order_id:
            self.logger.info(f"✅ Position closed: {symbol} - {action['reason']}")
        else:
            self.logger.warning(f"⚠️ Close order failed for {symbol}, removing from tracking")
        
        # Always remove from managed positions after close attempt
        if symbol in self.managed_positions:
            del self.managed_positions[symbol]
    
    def _move_stop(self, action: Dict) -> None:
        """Move stop loss level."""
        symbol = action["symbol"]
        new_stop = action["new_stop"]
        
        # Get position side to determine positionIdx for hedge mode
        position = self.managed_positions.get(symbol)
        if position:
            # Hedge mode: 1=Buy/Long, 2=Sell/Short
            position_idx = 1 if position.side == "Buy" else 2
        else:
            position_idx = 0  # Fallback for one-way mode
        
        try:
            self.client.client.set_trading_stop(
                category="linear",
                symbol=symbol,
                stopLoss=str(new_stop),
                positionIdx=position_idx
            )
            self.logger.info(f"✅ Stop moved: {symbol} → {new_stop:.2f}")
        except Exception as e:
            self.logger.error(f"Failed to move stop: {e}")
    
    def get_portfolio_risk(self, balance: float) -> Dict:
        """Calculate portfolio-wide risk metrics."""
        
        total_exposure = 0
        total_at_risk = 0
        
        for symbol, pos in self.managed_positions.items():
            position_value = pos.current_size * pos.entry_price
            exposure = position_value * pos.leverage
            total_exposure += exposure
            
            # Risk = distance to stop
            if pos.side == "Buy":
                risk_pct = (pos.entry_price - pos.stop_loss) / pos.entry_price
            else:
                risk_pct = (pos.stop_loss - pos.entry_price) / pos.entry_price
            
            at_risk = position_value * risk_pct * pos.leverage
            total_at_risk += at_risk
        
        return {
            "total_exposure": total_exposure,
            "exposure_ratio": total_exposure / balance if balance > 0 else 0,
            "total_at_risk": total_at_risk,
            "risk_ratio": total_at_risk / balance if balance > 0 else 0,
            "position_count": len(self.managed_positions)
        }
    
    def should_reduce_risk(self, balance: float) -> bool:
        """Check if portfolio risk is too high."""
        metrics = self.get_portfolio_risk(balance)
        
        # Max 50% of capital at risk
        if metrics["risk_ratio"] > 0.5:
            return True
        
        # Max 300% exposure
        if metrics["exposure_ratio"] > 3.0:
            return True
        
        return False
