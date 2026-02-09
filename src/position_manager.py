"""
💰 Advanced Position Management
===============================
Handles:
- Partial take profits
- Dynamic trailing stops
- Position scaling
- Break-even management
- Max drawdown protection
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class TakeProfitLevel:
    price: float
    size_pct: float  # Percentage of position to close
    triggered: bool = False


@dataclass
class ManagedPosition:
    symbol: str
    side: str
    entry_price: float
    current_size: float
    original_size: float
    leverage: int
    stop_loss: float
    trailing_active: bool
    trailing_stop: Optional[float]
    take_profits: List[TakeProfitLevel]
    highest_price: float  # For trailing (long)
    lowest_price: float   # For trailing (short)
    opened_at: datetime
    pnl_realized: float


class PositionManager:
    """Advanced position management system."""
    
    def __init__(self, config, client):
        self.config = config
        self.client = client
        self.logger = logging.getLogger(__name__)
        self.managed_positions: Dict[str, ManagedPosition] = {}
    
    def create_managed_position(self, symbol: str, side: str, entry_price: float,
                                size: float, leverage: int, atr: float) -> ManagedPosition:
        """Create a new managed position with TP levels."""
        
        # Calculate take profit levels based on ATR
        tp_levels = []
        
        if side == "Buy":
            # TP1: 1.5 ATR - 40% of position
            tp_levels.append(TakeProfitLevel(
                price=entry_price + (atr * 1.5),
                size_pct=0.40
            ))
            # TP2: 2.5 ATR - 30% of position
            tp_levels.append(TakeProfitLevel(
                price=entry_price + (atr * 2.5),
                size_pct=0.30
            ))
            # TP3: 4 ATR - 30% (let it run)
            tp_levels.append(TakeProfitLevel(
                price=entry_price + (atr * 4),
                size_pct=0.30
            ))
            
            stop_loss = entry_price - (atr * 2.0)
        else:
            tp_levels.append(TakeProfitLevel(
                price=entry_price - (atr * 1.5),
                size_pct=0.40
            ))
            tp_levels.append(TakeProfitLevel(
                price=entry_price - (atr * 2.5),
                size_pct=0.30
            ))
            tp_levels.append(TakeProfitLevel(
                price=entry_price - (atr * 4),
                size_pct=0.30
            ))
            
            stop_loss = entry_price + (atr * 2.0)
        
        position = ManagedPosition(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            current_size=size,
            original_size=size,
            leverage=leverage,
            stop_loss=stop_loss,
            trailing_active=False,
            trailing_stop=None,
            take_profits=tp_levels,
            highest_price=entry_price,
            lowest_price=entry_price,
            opened_at=datetime.now(),
            pnl_realized=0
        )
        
        self.managed_positions[symbol] = position
        return position
    
    def update_position(self, symbol: str, current_price: float) -> List[Dict]:
        """Update position and check for actions needed."""
        
        if symbol not in self.managed_positions:
            return []
        
        position = self.managed_positions[symbol]
        actions = []
        
        # Update price extremes
        if current_price > position.highest_price:
            position.highest_price = current_price
        if current_price < position.lowest_price:
            position.lowest_price = current_price
        
        # Check take profits
        for tp in position.take_profits:
            if tp.triggered:
                continue
            
            hit_tp = (position.side == "Buy" and current_price >= tp.price) or \
                     (position.side == "Sell" and current_price <= tp.price)
            
            if hit_tp:
                tp.triggered = True
                close_size = position.original_size * tp.size_pct
                
                actions.append({
                    "action": "partial_close",
                    "symbol": symbol,
                    "size": close_size,
                    "reason": f"TP hit at {tp.price:.2f}"
                })
                
                # Activate trailing after first TP
                if not position.trailing_active:
                    position.trailing_active = True
                    self.logger.info(f"🎯 Trailing stop activated for {symbol}")
        
        # Update trailing stop
        if position.trailing_active and position.current_size > 0:
            new_trailing = self._calculate_trailing_stop(position, current_price)
            
            if position.trailing_stop is None:
                position.trailing_stop = new_trailing
            else:
                # Only move trailing in profit direction
                if position.side == "Buy" and new_trailing > position.trailing_stop:
                    position.trailing_stop = new_trailing
                elif position.side == "Sell" and new_trailing < position.trailing_stop:
                    position.trailing_stop = new_trailing
            
            # Check if trailing stop hit
            trailing_hit = (position.side == "Buy" and current_price <= position.trailing_stop) or \
                          (position.side == "Sell" and current_price >= position.trailing_stop)
            
            if trailing_hit:
                actions.append({
                    "action": "close_all",
                    "symbol": symbol,
                    "size": position.current_size,
                    "reason": f"Trailing stop hit at {position.trailing_stop:.2f}"
                })
        
        # Check break-even move
        if not position.trailing_active and position.current_size > 0:
            be_distance = self._get_break_even_distance(position, current_price)
            
            if be_distance >= 0.015:  # 1.5% in profit
                # Move stop to break even
                actions.append({
                    "action": "move_stop",
                    "symbol": symbol,
                    "new_stop": position.entry_price,
                    "reason": "Moving stop to break-even"
                })
                position.stop_loss = position.entry_price
        
        return actions
    
    def _calculate_trailing_stop(self, position: ManagedPosition, 
                                  current_price: float) -> float:
        """Calculate new trailing stop level."""
        
        trail_pct = 0.015  # 1.5% trailing distance
        
        if position.side == "Buy":
            return position.highest_price * (1 - trail_pct)
        else:
            return position.lowest_price * (1 + trail_pct)
    
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
    
    def _close_position(self, action: Dict) -> None:
        """Close entire position."""
        symbol = action["symbol"]
        
        position = self.managed_positions.get(symbol)
        if not position:
            return
        
        close_side = "Sell" if position.side == "Buy" else "Buy"
        
        order_id = self.client.place_order(
            symbol=symbol,
            side=close_side,
            qty=position.current_size,
            reduce_only=True
        )
        
        if order_id:
            self.logger.info(f"✅ Position closed: {symbol} - {action['reason']}")
            del self.managed_positions[symbol]
    
    def _move_stop(self, action: Dict) -> None:
        """Move stop loss level."""
        symbol = action["symbol"]
        new_stop = action["new_stop"]
        
        try:
            self.client.client.set_trading_stop(
                category="linear",
                symbol=symbol,
                stopLoss=str(new_stop)
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
