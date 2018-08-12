# HitBTC-Arbitrage-Bot

The same as my Binance Arbitrage Bot but runs on HitBTC.

# how it works

In multiple threads, the bot loops a three part trade sequence which is 1) buy an alt coin on the ETH market 2) sell that alt coin on the BTC market 3) buy back ETH on the BTC market. It decides which alt coin to use based on current market data and user defined minimum EV per trade. It makes all trades by placing limit orders at the current best bid. Normally, the bot has to cancel the order corresponding to the first trade of the sequence and start over without it getting filled. This happens when it gets outbid, or the market data changes such that it no longer expects a profit from the current sequence. The other orders always get filled and this usually happens quickly.

# dependencies and use

No dependencies outside of standard library. To use, copy and paste your api private key and secret where it says at top of module. See part of code under `if __name__ == '__main__'` to see how to get the bot trading. You can also use the class `HitBTCArbBot` independent of the bot, as in the below command line examples. 

```
>>> from hitbtc_arb_bot import *
>>> a = HitBTCArbBot()
>>> a.subscribe_to_all_tickers()
>>> a.start()
>>> a.update_trading_balances()
>>> a.get_active_orders()
>>> help(a.get_pivot)
Help on method get_pivot in module hitbtc_arb_bot:

get_pivot(buy_at_ask=False, front_run=True) method of hitbtc_arb_bot.HitBTCArbBot instance
    returns pivot, best_ev, and best_ev_1
    pivot is an alt coin that is traded on both ETH and BTC markets
    best_ev is calculated assuming the following three part trade sequence: buy pivot with ETH at current best bid price, sell pivot to BTC at current best bid price, buy ETH with BTC at current best ask price
    best_ev_1 is calculated the same except uses best bid price for last trade
    returns the highest best_ev possible given and corresponding pivot and best_ev_1

>>> a.get_pivot()
('POE', 1.0037278708036663, 1.0040599722790198)
>>> a.occupied_alts['POE']
1
>>> a.symbols[:20]
['BCNBTC', 'BTCUSD', 'DASHBTC', 'DOGEBTC', 'DOGEUSD', 'DSHBTC', 'EMCBTC', 'ETHBTC', 'FCNBTC', 'LSKBTC', 'LTCBTC', 'LTCUSD', 'NXTBTC', 'SBDBTC', 'SCBTC', 'STEEMBTC', 'XDNBTC', 'XEMBTC', 'XMRBTC', 'ARDRBTC']
>>> a.get_bid_ask("ETHBTC")
(0.051358, 0.051378)
>>> a.get_bid_ask("ETHBTC")
(0.051355, 0.051361)
>>> a.round_price("ETHBTC", 0.051352122231)
0.051352
