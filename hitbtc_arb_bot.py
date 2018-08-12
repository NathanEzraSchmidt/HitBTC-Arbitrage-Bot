__author__ = 'Nathan Ezra Schmidt'
__email__ = 'nathanezraschmidt@gmail.com'

import threading
import json
import hashlib
import hmac
import time
import websocket
import requests
import uuid

key = "copy and paste here"
secret = "copy and paste here"

url = 'https://api.hitbtc.com'
stream_url = 'wss://api.hitbtc.com/api/2/ws'

# funtions for getting public info

def get_symbols():
    symbols = requests.get(url+"/api/1/public/symbols")
    return [i['symbol'] for i in symbols.json()['symbols']]

def get_ethbtc_alts(symbols):
    eth = [i[:-3] for i in symbols if i.endswith("ETH")]
    return [i[:-3] for i in symbols if (i.endswith("BTC") and i[:-3] in eth)]

def get_symbol_info():
    symbols = requests.get(url+"/api/1/public/symbols")
    return symbols.json()
    return [i['symbol'] for i in symbols.json()['symbols']]

def get_symbols_info_dict():
    """
    example return
        d['ETHBTC'] = 
        {'symbol': 'ETHBTC',
        'step': '0.000001',
        'lot': '0.001',
        'currency': 'BTC',
        'commodity': 'ETH',
        'takeLiquidityRate': '0.001',
        'provideLiquidityRate': '-0.0001'}
    """
    try:
        symbols = hit_symbols[:]
    except:
        symbols = requests.get(url+"/api/1/public/symbols").json()['symbols']
        
    d = {}
    
    for i in symbols:
        d[i['symbol']] = i
        d[i['symbol']]['stepLen'] = len(i['step']) - 2
        d[i['symbol']]['stepFloat'] = float(i['step'])
        d[i['symbol']]['lotFloat'] = float(i['lot'])
    return d

class HitBTCArbBot(threading.Thread):
    def __init__(self, min_ev=1.002,
                 starting_amount=0.1,
                 min_liquidity=.99,
                 quote_1='ETH',
                 quote_2='BTC',
                 key=key,
                 secret=secret,
                 base_url='wss://api.hitbtc.com/api/2/ws'):

        """
        min_ev is EV per trade
        starting_amount is amount of quote_1 to use for each trade
        min_liquidity is min liquidity for a market to have in order to be used
        """
        
        threading.Thread.__init__(self)

        self.update_trading_balances_lock = threading.Lock()
        self.active_orders_lock = threading.Lock()

        self.trading_balances_id = 2
        self.min_ev = min_ev
        self.starting_amount = starting_amount
        self.min_liquidity = min_liquidity
        self.quote_1, self.quote_2 = quote_1, quote_2
        self.key = key
        self.secret = secret
        self.base_url = base_url
        
        self.symbol_info_dict = get_symbols_info_dict()
        self.symbols = list(self.symbol_info_dict.keys())
        self.alts = get_ethbtc_alts(self.symbols)

        # start connection
        self.ws = websocket.create_connection(self.base_url)
        self.ws.connect(self.base_url)
        time.sleep(2)

        # login
        algo = 'HS256'
        nonce = str(round(time.time() * 1000))
        signature = hmac.new(secret.encode('UTF-8'), nonce.encode('UTF-8'), hashlib.sha256).hexdigest()
        payload = {'nonce': nonce, 'signature': signature}
        payload['algo'] = algo
        payload['pKey'] = key
        data = {"method":'login', 'params':payload, "id": int(10000*time.time())}
        self.ws.send(json.dumps(data))

        self.ticker_dict = {}
        self.order_status_dict = {}
        self.occupied_alts = {}
        for alt in self.alts:
            self.occupied_alts[alt] = 0
        self.buy_price_dict = {}
        self.sell_price_dict = {}
        self.trading_balances_dict = {}
        self.order_id_dict = {}
        self.subscribe_reports()

        self.ACTIVE_ORDERS_ID = 1
        self.error_msg = {'id':0}

    def get_liquid_alts(self):
        y = []
        for alt in self.alts:
            bid, ask = self.get_bid_ask(alt+"ETH")
            try:
                if bid/ask >= self.min_liquidity:
                    y.append(alt)
            except:
                continue
        self.alts = y[:]

    def clear_occupied_alts(self):
        for alt in self.occupied_alts:
            self.occupied_alts[alt] = 0

    def get_all_alts(self):
        self.alts = get_ethbtc_alts(self.symbols)

    def subscribe_to_all_tickers(self):
        for symbol in self.symbols:
            try:
                data = {"method": "subscribeTicker", "params": { "symbol": symbol }, "id": int(10000*time.time())}
                self.ws.send(json.dumps(data))
            except:
                pass
                
    def subscribe_reports(self):
        data = {'method':'subscribeReports', "params": {}, "id": int(10000*time.time())}
        self.ws.send(json.dumps(data))

    def get_active_orders(self):
        self.ACTIVE_ORDERS_ID = int(100000*time.time())
        data = {'method':'getOrders', "params": {}, "id": self.ACTIVE_ORDERS_ID}
        self.active_orders_lock.acquire()
        self.ws.send(json.dumps(data))
        while self.active_orders_lock.locked():
            pass
        
    def update_trading_balances(self):
        data = { "method": "getTradingBalance", "params": {}, "id": self.trading_balances_id}
        self.update_trading_balances_lock.acquire()
        self.ws.send(json.dumps(data))
        self.update_trading_balances_lock.acquire()
        self.update_trading_balances_lock.release()

    def round_quantity(self, symbol, quantity):
        quantity = float(quantity)
        lot = self.symbol_info_dict[symbol]['lotFloat']
        return round(lot*(int(quantity/lot)), 4)

    def round_price(self, symbol, price):
        return round(price, self.symbol_info_dict[symbol]['stepLen'])

    def place_new_order(self, symbol='ETHBTC', side='sell', quantity=0.1, price=.07, get_quantity=False):
        clientOrderId = str(uuid.uuid4()).replace('-','')
        if get_quantity:
            quantity /= price
        if quantity == 0:
            return 'error'
        price = self.round_price(symbol, price)
        order_id = int(10000*time.time())   
        data = {'method':'newOrder',
                'params':{
                'clientOrderId':clientOrderId,
                'symbol':symbol.upper(),
                'side':side,
                'quantity':quantity,
                'price':price },
                'id':order_id
                }
        self.ws.send(json.dumps(data))

        while True:
            if self.error_msg['id'] == order_id:
                return 'error'
                break
            try:
                if self.order_status_dict[symbol]['clientOrderId'] == clientOrderId:
                    break
            except:
                pass

    def cancel_order(self, symbol='ETHBTC'):
        if not symbol in self.order_status_dict:
            return
        if self.order_status_dict[symbol]['status'] in ('filled', 'suspended', 'expired'):
            return
        clientOrderId = self.order_status_dict[symbol]["clientOrderId"]
        data = { "method": "cancelOrder",
                 "params": { "clientOrderId": clientOrderId },
                 "id": int(10000*time.time()) }
        self.ws.send(json.dumps(data))
        while self.order_status_dict[symbol]['status'] != 'canceled':
            pass

    def cancel_all_orders(self, get_active_orders=False):
        if get_active_orders:
            self.get_active_orders()
        for order in self.active_orders:
            data = { "method": "cancelOrder",
                 "params": { "clientOrderId": order['clientOrderId'] },
                 "id": 1 }
            self.ws.send(json.dumps(data))   

    def get_bid_ask(self, symbol):
        try:
            return float(self.ticker_dict[symbol]['bid']), float(self.ticker_dict[symbol]['ask'])
        except:
            return None, None

    def get_pivot(self, buy_at_ask=False, front_run=True):
        """
        returns pivot, best_ev, and best_ev_1
        pivot is an alt coin that is traded on both ETH and BTC markets
        best_ev is calculated assuming the following three part trade sequence: buy pivot with ETH at current best bid price, sell pivot to BTC at current best bid price, buy ETH with BTC at current best ask price
        best_ev_1 is calculated the same except uses best bid price for last trade
        returns the highest best_ev possible given and corresponding pivot and best_ev_1
        """
        bid, ask = None, None
        while bid == None or ask == None:
            bid, ask = self.get_bid_ask("ETHBTC")
        best_ev = 0
        pivot = 0
        for alt in self.alts:
            if self.occupied_alts[alt]:
                continue
            try:
                buy_price = self.get_bid_ask(alt+"ETH")[int(buy_at_ask)]
                sell_price = self.get_bid_ask(alt+"BTC")[0]
                if buy_at_ask == False and front_run == True:
                    buy_price += self.symbol_info_dict[alt+"ETH"]['stepFloat']
                buy_price = self.round_price(alt+'ETH', buy_price)
                sell_price = self.round_price(alt+'BTC', sell_price)
                assert (isinstance(buy_price, float) and isinstance(sell_price, float))
            except:
                continue
            if buy_at_ask == False and self.get_bid_ask(alt+"ETH")[0] / self.get_bid_ask(alt+"ETH")[1] < self.min_liquidity:
                continue
            ev = (sell_price/buy_price)/ask
            if ev > self.min_ev  and ev > best_ev:
                best_ev = ev
                best_ev_1 = (sell_price/buy_price)/bid
                pivot = alt
                self.buy_price_dict[pivot] = buy_price
                self.sell_price_dict[pivot] = sell_price
        if best_ev:
            self.occupied_alts[pivot] = 1
            return pivot, best_ev, best_ev_1
        else:
            return False, False, False
    
    def buy_pivot(self):
        pivot = False
        TIMEOUT = 90
        while pivot == False:
            pivot = self.get_pivot(False)[0]
        symbol = pivot + 'ETH'
        quantity = .1/self.buy_price_dict[pivot]
        price = self.buy_price_dict[pivot]
        x = self.place_new_order(symbol, 'buy', quantity, price)
        if x == 'error':
            self.occupied_alts[pivot] = 0
            self.update_trading_balances()
            return 'error'
        start_time = time.time()
        while True:
            if self.order_status_dict[symbol]['status'] != 'new':
                break
            if price < self.get_bid_ask(symbol)[0]:
                break
            if self.sell_price_dict[pivot] > self.get_bid_ask(pivot+'BTC')[0]:
                break
            if time.time() - start_time > TIMEOUT:
                break
        self.cancel_order(symbol)
        return pivot

    def sell_pivot(self, pivot, sell_at_bid=False, sell_at_ask=False, front_run=False):
        symbol = pivot + "BTC"
        if sell_at_bid:
            price = self.get_bid_ask(symbol)[0]
        elif sell_at_ask:
            price = self.get_bid_ask(symbol)[1]
        else:
            price = self.sell_price_dict[pivot]
        self.update_trading_balances()
        alt_balance = float(self.trading_balances_dict[pivot][0])
        quantity = self.round_quantity(symbol, alt_balance)
        while True:
            if quantity == 0:
                break
            self.place_new_order(symbol, 'sell', quantity, price)
            while price <= self.get_bid_ask(symbol)[1] and self.order_status_dict[symbol]['status'] != 'filled':
                pass
            price = self.get_bid_ask(symbol)[1]
            if front_run:
                price -= self.symbol_info_dict[symbol]['stepFloat']
            self.cancel_order(symbol)
            self.update_trading_balances()
            alt_balance = self.trading_balances_dict[pivot][0]
            quantity = self.round_quantity(symbol, alt_balance)
            
        self.occupied_alts[pivot] = 0
        self.update_trading_balances()
        
    def buy_and_cancel(self, symbol, quantity, price, **kwargs):
        x = self.place_new_order(symbol, 'buy', quantity, price, get_quantity=False)
        if x == 'error':
            return 'error'
        while True:
            if 'status' in kwargs and self.order_status_dict[symbol]['status'] in kwargs['status']:
                if self.order_status_dict[symbol]['status'] == 'filled':
                    return 'filled'
                break
            if 'outbid' in kwargs and price < self.get_bid_ask(symbol)[0]:
                break
        self.cancel_order(symbol)
        return 'canceled'
        
    def buy_with_all_quote(self, base='ETH', quote='BTC', front_run=True, buy_at_ask=False):
        symbol = base + quote
        while True:
            self.update_trading_balances()
            price = self.get_bid_ask(symbol)[int(buy_at_ask)]
            if front_run:
                price += self.symbol_info_dict[symbol]['stepFloat']
            quantity = self.round_quantity(symbol, float(self.trading_balances_dict[quote][0]) / price)
            x = self.buy_and_cancel(symbol, quantity, price, status=['suspended', 'filled', 'expired', 'canceled'], outbid=True)
            if x in ('error', 'filled'):
                return
            
    def arb_eth(self):
        pivot = self.buy_pivot()
        if pivot == 'error':
            return
        self.sell_pivot(pivot)
        self.buy_with_all_quote()

    def arb_eth_loop(self):
        while True:
            self.arb_eth()
        
    def buy_sell(self):
        self.sell_pivot(self.buy_pivot())

    def buy_sell_loop(self):
        while True:
            self.buy_sell()
            
    def run(self): # overwrite run method of Thread
        while True:
            x = json.loads(self.ws.recv())
            if 'params' in x and 'ask' in x['params']:
                p = x['params']
                self.ticker_dict[p['symbol']] = p
                
            if 'error' in x:     
                self.error_msg = x

            if 'method' in x and x['method'] == 'report':
                p = x['params']
                self.order_status_dict[p['symbol']] = p
                
            if 'id' in x and x['id'] == self.ACTIVE_ORDERS_ID:
                r = x['result']
                for order in r:
                    self.order_status_dict[order['symbol']] = order
                self.active_orders = r
                self.active_orders_lock.release()
                
            if 'id' in x and x['id'] == self.trading_balances_id:
                balances = x['result']
                for balance in balances:
                    self.trading_balances_dict[balance['currency']] = tuple((balance['available'], balance['reserved']))
                self.update_trading_balances_lock.release()

if __name__ == '__main__':
    a = HitBTCArbBot()
    a.subscribe_to_all_tickers()
    a.start() # from Thread, calls a.run
    time.sleep(1)
    a.update_trading_balances()
    a.get_active_orders() # to update a.order_status_dict and a.active_orders

    thread_num = 4
    for i in range(thread_num):
        threading.Thread(target=a.arb_eth_loop).start()    
