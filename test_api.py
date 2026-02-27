#!/usr/bin/env python3
"""Quick API test - place and cancel order"""

import time
import hmac
import hashlib
import requests

API_KEY = "WHd0XVYVzafl9RNMA6"
API_SECRET = "PBOsYg4ZoydbDyw0QxSIkeeqfLPdckkUk0be"
BASE_URL = "https://api.bybit.com"

def sign_request(params):
    """Sign API request"""
    timestamp = str(int(time.time() * 1000))
    params['api_key'] = API_KEY
    params['timestamp'] = timestamp
    
    param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
    sign = hmac.new(
        API_SECRET.encode('utf-8'),
        param_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params['sign'] = sign
    return params

def get_headers():
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    
    return {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "Content-Type": "application/json"
    }

def sign_v5(params_str, timestamp):
    sign_str = f"{timestamp}{API_KEY}{5000}{params_str}"
    return hmac.new(
        API_SECRET.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def test_order():
    """Test placing and canceling a small order"""
    
    # Get current BNB price first
    url = f"{BASE_URL}/v5/market/tickers?category=linear&symbol=BNBUSDT"
    resp = requests.get(url)
    data = resp.json()
    
    if data['retCode'] != 0:
        print(f"❌ Failed to get price: {data}")
        return False
    
    current_price = float(data['result']['list'][0]['lastPrice'])
    print(f"📊 Current BNBUSDT price: ${current_price}")
    
    # Place limit order 10% below market (won't fill)
    test_price = str(round(current_price * 0.85, 2))  # 15% below
    
    # V5 API order
    timestamp = str(int(time.time() * 1000))
    
    order_params = {
        "category": "linear",
        "symbol": "BNBUSDT",
        "side": "Buy",
        "orderType": "Limit",
        "qty": "0.1",  # Minimum qty
        "price": test_price,
        "timeInForce": "GTC",
        "positionIdx": 1  # 1=Buy side in hedge mode, 2=Sell side
    }
    
    import json
    params_str = json.dumps(order_params)
    signature = sign_v5(params_str, timestamp)
    
    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": "5000",
        "X-BAPI-SIGN": signature,
        "Content-Type": "application/json"
    }
    
    print(f"📝 Placing test order: Buy 0.1 BNB @ ${test_price}")
    
    resp = requests.post(
        f"{BASE_URL}/v5/order/create",
        headers=headers,
        json=order_params
    )
    
    data = resp.json()
    print(f"Response: {data}")
    
    if data['retCode'] == 0:
        order_id = data['result']['orderId']
        print(f"✅ Order placed! ID: {order_id}")
        
        # Cancel immediately
        time.sleep(0.5)
        
        cancel_params = {
            "category": "linear",
            "symbol": "BNBUSDT",
            "orderId": order_id
        }
        
        timestamp = str(int(time.time() * 1000))
        params_str = json.dumps(cancel_params)
        signature = sign_v5(params_str, timestamp)
        
        headers["X-BAPI-TIMESTAMP"] = timestamp
        headers["X-BAPI-SIGN"] = signature
        
        resp = requests.post(
            f"{BASE_URL}/v5/order/cancel",
            headers=headers,
            json=cancel_params
        )
        
        cancel_data = resp.json()
        if cancel_data['retCode'] == 0:
            print(f"✅ Order cancelled successfully!")
            print(f"\n🎉 API TEST PASSED - Trading permissions work!")
            return True
        else:
            print(f"⚠️ Cancel failed: {cancel_data}")
            return False
    else:
        print(f"❌ Order failed: {data}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Bybit API Trading Permissions...")
    print("=" * 50)
    test_order()
