# HitBTC-Arbitrage-Bot

The same as my Binance Arbitrage Bot but runs on HitBTC.

# Binance-Arbitrage-Bot

Bot that arbitrages between the ETH and BTC markets on Binance with the goal of winning ETH. 

# how it works

In multiple threads, the bot loops a three part trade sequence which is 1) buy an alt coin on the ETH market 2) sell that alt coin on the BTC market 3) buy back ETH on the BTC market. It decides which alt coin to use based on current market data and user defined minimum expected roi per trade (see `get_pivot` method of the `BinanceArbBot` class). It makes all trades by placing limit orders at the current best bid. Normally, the bot has to cancel the order corresponding to the first trade of the sequence and start over without it getting filled. This happens when it gets outbid, or the market data changes such that it no longer expects a profit from the current sequence. The other trades usually execute quickly, however, and the their corresponding orders should always get filled.
