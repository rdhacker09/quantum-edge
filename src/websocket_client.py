"""
⚡ WebSocket Client for Real-Time Data
======================================
High-speed market data streaming:
- Orderbook updates
- Trades (tick data)
- Klines
- Position updates
"""

import asyncio
import json
import logging
import time
import hmac
import hashlib
from typing import Dict, Callable, Optional, List
from threading import Thread
from collections import defaultdict

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class BybitWebSocket:
    """WebSocket client for real-time Bybit data."""
    
    # Bybit WebSocket endpoints
    MAINNET_PUBLIC = "wss://stream.bybit.com/v5/public/linear"
    MAINNET_PRIVATE = "wss://stream.bybit.com/v5/private"
    TESTNET_PUBLIC = "wss://stream-testnet.bybit.com/v5/public/linear"
    TESTNET_PRIVATE = "wss://stream-testnet.bybit.com/v5/private"
    
    def __init__(self, api_key: str = None, api_secret: str = None, 
                 testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.logger = logging.getLogger(__name__)
        
        self.public_url = self.TESTNET_PUBLIC if testnet else self.MAINNET_PUBLIC
        self.private_url = self.TESTNET_PRIVATE if testnet else self.MAINNET_PRIVATE
        
        self._public_ws = None
        self._private_ws = None
        self._running = False
        self._loop = None
        self._thread = None
        
        # Data stores
        self.orderbooks: Dict[str, Dict] = defaultdict(dict)
        self.tickers: Dict[str, Dict] = {}
        self.klines: Dict[str, List] = defaultdict(list)
        self.positions: Dict[str, Dict] = {}
        self.executions: List[Dict] = []
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
    
    def _generate_signature(self, timestamp: int) -> str:
        """Generate authentication signature."""
        param_str = f"GET/realtime{timestamp}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _auth_message(self) -> Dict:
        """Create authentication message."""
        timestamp = int(time.time() * 1000)
        signature = self._generate_signature(timestamp)
        
        return {
            "op": "auth",
            "args": [self.api_key, timestamp, signature]
        }
    
    def on(self, event: str, callback: Callable):
        """Register callback for event."""
        self._callbacks[event].append(callback)
    
    def _emit(self, event: str, data: Dict):
        """Emit event to callbacks."""
        for callback in self._callbacks[event]:
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")
    
    async def _handle_public_message(self, message: str):
        """Process public WebSocket message."""
        try:
            data = json.loads(message)
            
            topic = data.get('topic', '')
            
            if 'orderbook' in topic:
                symbol = topic.split('.')[-1]
                self.orderbooks[symbol] = data.get('data', {})
                self._emit('orderbook', {'symbol': symbol, 'data': data['data']})
                
            elif 'tickers' in topic:
                symbol = topic.split('.')[-1]
                self.tickers[symbol] = data.get('data', {})
                self._emit('ticker', {'symbol': symbol, 'data': data['data']})
                
            elif 'kline' in topic:
                parts = topic.split('.')
                interval = parts[1]
                symbol = parts[2]
                kline_data = data.get('data', [])
                if kline_data:
                    key = f"{symbol}_{interval}"
                    self.klines[key] = kline_data
                    self._emit('kline', {'symbol': symbol, 'interval': interval, 'data': kline_data})
                
            elif 'publicTrade' in topic:
                symbol = topic.split('.')[-1]
                self._emit('trade', {'symbol': symbol, 'data': data.get('data', [])})
                
        except Exception as e:
            self.logger.error(f"Error processing public message: {e}")
    
    async def _handle_private_message(self, message: str):
        """Process private WebSocket message."""
        try:
            data = json.loads(message)
            
            topic = data.get('topic', '')
            
            if topic == 'position':
                for pos in data.get('data', []):
                    symbol = pos.get('symbol')
                    if symbol:
                        self.positions[symbol] = pos
                        self._emit('position', pos)
                        
            elif topic == 'execution':
                for exec_data in data.get('data', []):
                    self.executions.append(exec_data)
                    self._emit('execution', exec_data)
                    
            elif topic == 'order':
                for order in data.get('data', []):
                    self._emit('order', order)
                    
            elif topic == 'wallet':
                self._emit('wallet', data.get('data', {}))
                
        except Exception as e:
            self.logger.error(f"Error processing private message: {e}")
    
    async def _public_handler(self, symbols: List[str]):
        """Handle public WebSocket connection."""
        while self._running:
            try:
                async with websockets.connect(self.public_url) as ws:
                    self._public_ws = ws
                    self.logger.info("📡 Public WebSocket connected")
                    
                    # Subscribe to channels
                    topics = []
                    for symbol in symbols:
                        topics.extend([
                            f"tickers.{symbol}",
                            f"kline.5.{symbol}",
                            f"orderbook.50.{symbol}"
                        ])
                    
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": topics
                    }))
                    
                    # Process messages
                    async for message in ws:
                        if not self._running:
                            break
                        await self._handle_public_message(message)
                        
            except Exception as e:
                self.logger.error(f"Public WS error: {e}")
                if self._running:
                    await asyncio.sleep(5)
    
    async def _private_handler(self):
        """Handle private WebSocket connection."""
        if not self.api_key or not self.api_secret:
            return
        
        while self._running:
            try:
                async with websockets.connect(self.private_url) as ws:
                    self._private_ws = ws
                    self.logger.info("🔐 Private WebSocket connected")
                    
                    # Authenticate
                    auth_msg = await self._auth_message()
                    await ws.send(json.dumps(auth_msg))
                    
                    # Wait for auth response
                    response = await ws.recv()
                    auth_result = json.loads(response)
                    
                    if auth_result.get('success'):
                        self.logger.info("✅ WebSocket authenticated")
                        
                        # Subscribe to private channels
                        await ws.send(json.dumps({
                            "op": "subscribe",
                            "args": ["position", "execution", "order", "wallet"]
                        }))
                        
                        # Process messages
                        async for message in ws:
                            if not self._running:
                                break
                            await self._handle_private_message(message)
                    else:
                        self.logger.error("❌ WebSocket auth failed")
                        await asyncio.sleep(10)
                        
            except Exception as e:
                self.logger.error(f"Private WS error: {e}")
                if self._running:
                    await asyncio.sleep(5)
    
    async def _run(self, symbols: List[str]):
        """Main WebSocket runner."""
        tasks = [self._public_handler(symbols)]
        
        if self.api_key and self.api_secret:
            tasks.append(self._private_handler())
        
        await asyncio.gather(*tasks)
    
    def start(self, symbols: List[str]):
        """Start WebSocket connections in background."""
        if not WEBSOCKETS_AVAILABLE:
            self.logger.warning("websockets not installed - using REST only")
            return
        
        self._running = True
        self._loop = asyncio.new_event_loop()
        
        def run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run(symbols))
        
        self._thread = Thread(target=run_loop, daemon=True)
        self._thread.start()
        
        self.logger.info("⚡ WebSocket started")
    
    def stop(self):
        """Stop WebSocket connections."""
        self._running = False
        
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self._thread:
            self._thread.join(timeout=5)
        
        self.logger.info("WebSocket stopped")
    
    def get_best_bid_ask(self, symbol: str) -> Optional[Dict]:
        """Get best bid/ask from orderbook."""
        ob = self.orderbooks.get(symbol)
        if not ob:
            return None
        
        bids = ob.get('b', [])
        asks = ob.get('a', [])
        
        if bids and asks:
            return {
                'bid': float(bids[0][0]),
                'bid_size': float(bids[0][1]),
                'ask': float(asks[0][0]),
                'ask_size': float(asks[0][1]),
                'spread': float(asks[0][0]) - float(bids[0][0])
            }
        return None
    
    def get_orderbook_imbalance(self, symbol: str, levels: int = 10) -> float:
        """Calculate orderbook imbalance (-1 to 1)."""
        ob = self.orderbooks.get(symbol)
        if not ob:
            return 0
        
        bids = ob.get('b', [])[:levels]
        asks = ob.get('a', [])[:levels]
        
        bid_volume = sum(float(b[1]) for b in bids)
        ask_volume = sum(float(a[1]) for a in asks)
        
        total = bid_volume + ask_volume
        if total == 0:
            return 0
        
        # Positive = more bids (bullish), Negative = more asks (bearish)
        return (bid_volume - ask_volume) / total
