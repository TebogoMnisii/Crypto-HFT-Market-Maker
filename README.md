Crypto HFT Market Maker
A high-frequency trading market-making bot for cryptocurrency markets, specifically optimized for the Binance exchange.
Overview
This project implements an asynchronous cryptocurrency market-making system in Python that utilizes Binance's WebSocket API for real-time limit order book (LOB) data. The bot dynamically adjusts spreads based on real-time volatility calculations and features robust error handling for continuous operation.
Features

Real-time order book synchronization with Binance
Dynamic spread adjustment based on market volatility
Asynchronous architecture for low-latency operations
Fault-tolerance with automatic reconnection logic
Statistical processing using NumPy and SciPy

Requirements

Python 3.7+
websockets
aiohttp
numpy
scipy

Installation
bashgit clone https://github.com/yourusername/crypto-hft-market-maker.git
cd crypto-hft-market-maker
pip install -r requirements.txt
Usage
bashpython market_maker.py
By default, the bot trades on the BTCUSDT pair. You can modify the configuration variables at the top of the script to change parameters like:

Trading pair
Initial/Min/Max spread values
Volatility multiplier

Configuration
The main configuration parameters can be found at the top of the market_maker.py file:
pythonSYMBOL = 'BTCUSDT'
WS_URL = f"wss://stream.binance.com:9443/ws/{SYMBOL.lower()}@depth"
INITIAL_SPREAD = 0.002  # 0.2%
MIN_SPREAD = 0.001      # 0.1%
MAX_SPREAD = 0.01       # 1%

Disclaimer
This software is for educational purposes only. Use at your own risk. Cryptocurrency trading involves significant risk and you can lose your invested capital. The authors are not responsible for any financial losses incurred using this software.
