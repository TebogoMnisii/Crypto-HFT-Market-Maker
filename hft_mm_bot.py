#!/usr/bin/env python3
import asyncio
import json
import logging
import numpy as np
import websockets
import aiohttp
from scipy.ndimage import uniform_filter1d

# Configuration
SYMBOL = 'BTCUSDT'
WS_URL = f"wss://stream.binance.com:9443/ws/{SYMBOL.lower()}@depth"
INITIAL_SPREAD = 0.002  # 0.2%
MIN_SPREAD = 0.001      # 0.1%
MAX_SPREAD = 0.01       # 1%

class MarketMaker:
    def __init__(self):
        self.spread = INITIAL_SPREAD
        self.mid_prices = []
        self.bids = []
        self.asks = []
        self.last_update_id = None
        self.first_processed = False

    def update_spread(self, volatility):
        self.spread = max(MIN_SPREAD, min(MAX_SPREAD, 0.003 * volatility))

    def process_snapshot(self, data):
        """Process initial order book snapshot"""
        self.bids = sorted([[float(p), float(q)] for p, q in data['bids']], reverse=True)
        self.asks = sorted([[float(p), float(q)] for p, q in data['asks']])
        self.last_update_id = data['lastUpdateId']
        logging.info(f"Snapshot processed, lastUpdateId: {self.last_update_id}")

    def process_update(self, data):
        """Process incremental order book updates"""
        # First update needs special handling per Binance docs
        if not self.first_processed:
            if data['U'] <= self.last_update_id + 1 and data['u'] >= self.last_update_id + 1:
                logging.info(f"First update processed: U={data['U']}, u={data['u']}")
                self.last_update_id = data['u']
                self.first_processed = True
                self.apply_changes(data)
            return
        
        # Check for missing updates
        if data['U'] <= self.last_update_id + 1:
            if data['u'] >= self.last_update_id + 1:
                self.apply_changes(data)
                self.last_update_id = data['u']
            # else update is older than current state, ignore it
        else:
            # Gap detected
            raise ValueError(f"Missing updates: last_update_id={self.last_update_id}, update U={data['U']}")

    def apply_changes(self, data):
        """Apply the changes from update data"""
        # Process bid updates
        for price, qty in data['b']:
            price, qty = float(price), float(qty)
            if qty == 0:
                self.bids = [b for b in self.bids if b[0] != price]
            else:
                # Find and update existing price level or add new one
                existing = next((b for b in self.bids if b[0] == price), None)
                if existing:
                    existing[1] = qty
                else:
                    self.bids.append([price, qty])
        self.bids.sort(reverse=True)
        
        # Process ask updates
        for price, qty in data['a']:
            price, qty = float(price), float(qty)
            if qty == 0:
                self.asks = [a for a in self.asks if a[0] != price]
            else:
                # Find and update existing price level or add new one
                existing = next((a for a in self.asks if a[0] == price), None)
                if existing:
                    existing[1] = qty
                else:
                    self.asks.append([price, qty])
        self.asks.sort()

async def handle_messages(ws, mm):
    """Continuous message processing"""
    async for message in ws:
        try:
            data = json.loads(message)
            
            # Process depth update event
            if isinstance(data, dict) and data.get('e') == 'depthUpdate':
                try:
                    mm.process_update(data)
                    
                    if mm.bids and mm.asks and mm.first_processed:
                        best_bid, best_ask = mm.bids[0][0], mm.asks[0][0]
                        mid = (best_bid + best_ask) / 2
                        mm.mid_prices.append(mid)
                        
                        # Calculate volatility
                        if len(mm.mid_prices) > 20:
                            prices = uniform_filter1d(np.array(mm.mid_prices[-20:]), size=5)
                            returns = np.diff(prices) / prices[:-1]
                            vol = np.std(returns)
                            mm.update_spread(vol)
                            
                            # Calculate our prices
                            our_bid = mid * (1 - mm.spread/2)
                            our_ask = mid * (1 + mm.spread/2)
                            
                            logging.info(
                                f"OUR BID: {our_bid:.2f} | "
                                f"OUR ASK: {our_ask:.2f} | "
                                f"Spread: {mm.spread*100:.2f}% | "
                                f"Best Bid: {best_bid:.2f} | Best Ask: {best_ask:.2f}"
                            )
                except ValueError as ve:
                    # Missing updates error - need to reconnect
                    raise ve
                    
        except json.JSONDecodeError:
            logging.error("Invalid JSON message")
        except ValueError as ve:
            # Propagate valueError upward to force reconnection
            raise ve
        except Exception as e:
            logging.error(f"Processing error: {str(e)[:200]}")

async def run_bot():
    """Main trading loop"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('hft_bot.log'),
            logging.StreamHandler()
        ]
    )
    
    while True:
        mm = MarketMaker()  # Create new instance on each reconnect
        
        try:
            # Get initial snapshot first via REST API
            async with aiohttp.ClientSession() as session:
                snapshot_url = f"https://api.binance.com/api/v3/depth?symbol={SYMBOL}&limit=1000"
                async with session.get(snapshot_url) as response:
                    if response.status == 200:
                        snapshot_data = await response.json()
                        mm.process_snapshot(snapshot_data)
                        logging.info("Initial order book snapshot received")
                    else:
                        logging.error(f"Failed to get order book snapshot: {response.status}")
                        await asyncio.sleep(5)
                        continue
            
            # Connect to WebSocket for live updates
            async with websockets.connect(WS_URL) as ws:
                logging.info("Connected to Binance WebSocket")
                
                # Subscribe to live updates
                await ws.send(json.dumps({
                    "method": "SUBSCRIBE",
                    "params": [f"{SYMBOL.lower()}@depth"],
                    "id": 1
                }))
                subscription_response = await ws.recv()  # Consume subscription response
                logging.info(f"Subscription response: {subscription_response}")
                
                # Process messages
                await handle_messages(ws, mm)
                
        except (websockets.exceptions.ConnectionClosed, ValueError) as e:
            # Handle both connection issues and order book sequence issues
            if isinstance(e, ValueError):
                logging.warning(f"Order book sync issue: {str(e)} - reconnecting...")
            else:
                logging.warning(f"Connection closed: {str(e)} - reconnecting...")
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Error: {str(e)[:200]} - reconnecting...")
            await asyncio.sleep(5)

async def main():
    print(f"Starting HFT Market Maker for {SYMBOL}...")
    await run_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")