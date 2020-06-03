import alpaca_trade_api as alpaca
from time import sleep
from datetime import datetime, timedelta
import numpy as np
from polygon import AlpacaSocket
from math import floor
import sys
import re
import json
from threading import Thread
from selection import get_symbols
from sms import SMS
from config import KEY, SECRET, EMAIL, PASSWORD


date = lambda: str(datetime.now())[:10]
timestamp = lambda: str(datetime.now())[11:19]
nano = 1000000000

def rnd(x, r):
    return np.round(x, r)

def market_close(unix):
	t = datetime.fromtimestamp(unix)
	y, m, d = [int(s) for s in date().split('-')]
	return((datetime(y, m, d, 16, 0, 0) - t).seconds)

def read_data(f):
    with open(f, 'r') as df:
        return json.loads(df.read())

def dump_data(f, d):
    with open(f, 'w') as df:
        json.dump(d, df, indent=4)

def until_open():
	now = datetime.now()
	y, m, d = [int(s) for s in str(now)[:10].split('-')]
	market_open = datetime(y, m, d, 9, 30)
	return ((market_open - now).seconds)


class MeanRevertBot(object):

	def __init__(self, sandbox=False, risk=1.5, max_positions=None, funds=5000, wait=False, alert=True):
		base = 'https://api.alpaca.markets'
		if sandbox: base = 'https://paper-api.alpaca.markets'
		self.client = alpaca.REST(KEY, SECRET, base)
		self.account = self.client.get_account()
		self.mp = max_positions
		self.funds = funds
		self.alert = alert
		self.margin = get_symbols(risk=risk, s=2)
		self.tickers = {}
		self.positions = 0
		self.pending = []
		self.active = {}
		self.number = 5169724212
		self.symbols = [s for s in self.margin]
		if self.mp is None: self.mp = int((len(self.symbols)/2.5))
		print(f'Symbols Chosen: {self.symbols}')
		for position in self.client.list_positions():
			self.positions += 1
			sym = position.symbol
			pos = position.side
			lp = float(position.avg_entry_price)
			qty = int(position.qty)
			self.funds -= lp * qty
			if pos == 'short':
				self.active[sym] = {'t': 'short', 'g': lp * (1.01), 's': qty, 'p': lp}
			else:
				self.active[sym] = {'t': 'long', 'g': lp * (1.01), 's': qty, 'p': lp}
		for sym in self.active:
			self.symbols.append(sym)
		print(f'Max Positions: {self.mp} | Funds: {self.funds}$ | Aim: Dynamic | Risk Factor: {risk} | Alerting: {self.alert}')
		if wait: self._wait()
		self.ws_client = AlpacaSocket(key=KEY, secret=SECRET, tickers=self.symbols, on_message=self.ticker)
		self.sms_client = SMS(EMAIL, PASSWORD)
		for symbol in self.symbols:
			self.tickers[symbol] = {'o': 0, 'l': 0, 'h': 0}
		self.ws_client.start()

	def _wait(self):
		time = until_open()
		print(f'Sleeping {time} seconds until Market Open')
		sleep(time)
		now = str(datetime.now())
		print(f'Starting Bot at {now}')

	def manage_position(self, message, s, p, pc, po, time):
		t = self.active[s]['t']
		g = self.active[s]['g']
		q = self.active[s]['s']
		bp = self.active[s]['p']
		if market_close(int(time/nano)) < 300:
			self.account = self.client.get_account()
			gain = float(self.account.equity) - float(self.account.last_equity)
			if gain > self.funds * 1.01:
				print('Positive Gain, Attempting to Liquidate Assets')
				self._liquidate()

			sys.exit(1)
		if t == 'long':
			if p >= g:
				self.pending.append(s)
				print(f'\n[+] Trying to Execute Long for [{s}] {p} per share | Open {po} [{pc}%]')
				Thread(target=self.sell, args=(s, q, True)).start()
		elif t == 'short':
			if p <= g:
				self.pending.append(s)
				print(f'\n[+] Trying to Execute Short for [{s}] at {p} per share | Open {po} [{pc}%]')
				Thread(target=self.buy, args=(s, q, True)).start()

	def manage_ticker(self, message, s, p, pc, po):
		available = self.funds/(self.mp - self.positions)
		if po == 0: 
			self.tickers[s]['o'] = p
			self.tickers[s]['l'] = p * (1 - self.margin[s][2])
			self.tickers[s]['h'] = p * (1 + self.margin[s][3])
			po = self.tickers[s]['o']
		l = self.tickers[s]['l']
		h = self.tickers[s]['h']
		print(l, h, self.tickers[s]['o'])
		q = floor(available/p)
		if p <= l:
			self.pending.append(s)
			print(f'\n[+] Trying to Buy {s} at {p} per share | Open: {po} [Change: {pc}%]')
			Thread(target=self.buy, args=(s, q,)).start()
		if p >= h:
			self.pending.append(s)
			print(f'\n[-] Trying to Short {s} shares at {p} per share | Open: {po} [Change: {pc}%]')
			Thread(target=self.sell, args=(s, q,)).start()

	def ticker(self, msg):
		message = json.loads(msg)['data']
		print(message)
		if 'ev' in message:
			if message['ev'] == 'T':
				time = message['t']
				s = message['T']
				p = float(message['p'])
				po = self.tickers[s]['o']
				pc = 0
				if po != 0: pc = rnd(((p - po)/po) * 100, 3)
				if s not in self.pending:
					if s in self.active:
						self.manage_position(message, s, p, pc, po, time)
					elif self.positions < self.mp:
						self.manage_ticker(message, s, p, pc, po)
		else:
			print(message)

	def buy(self, symbol, qty, exit=False):
		order = self.client.submit_order(symbol=symbol, side='buy', type='market', qty=abs(qty), time_in_force='day')
		_id = order.id
		while self._fill(_id) is None:
			sleep(.5)
		lp = float(self._fill(_id))
		self.pending.remove(symbol)
		if not exit:
			self.positions += 1
			self.funds -= (qty * lp)
			self.active[symbol] = {'t': 'long', 'g': lp * (1 + 2 * self.margin[symbol][0]), 's': abs(qty), 'p': lp}
		else:
			self.active[symbol]['t'] = 'done'
		alert = f'({timestamp()}) [+] Bought {qty} shares of {symbol} at {lp} per share \n'
		print(alert)
		self.sms_client.send_message(self.number, alert)
		return

	def sell(self, symbol, qty, exit=False):
		order = self.client.submit_order(symbol=symbol, side='sell', type='market', qty=abs(qty), time_in_force='day')
		_id = order.id
		while self._fill(_id) is None:
			sleep(.5)
		lp = float(self._fill(_id))
		self.pending.remove(symbol)
		if not exit:
			self.positions += 1
			self.funds -= (qty * lp)
			self.active[symbol] = {'t': 'short', 'g': lp * (1 - 2 * self.margin[symbol][1]), 's': abs(qty), 'p': lp}
		else:
			self.active[symbol]['t'] = 'done'
		alert = f'({timestamp()}) [+] Sold {qty} shares of {symbol} at {lp} per share \n'
		print(alert)
		self.sms_client.send_message(self.number, alert)
		return

	def _fill(self, _id):
		return self.client.get_order(_id).filled_avg_price

	def _liquidate(self):
		for position in self.client.list_positions():
			qty = int(position.qty)
			s = position.symbol
			if qty > 0:
				Thread(target=self.sell, args=(s, q, True)).start()
			else:
				Thread(target=self.buy, args=(s, q, True)).start()

bot = MeanRevertBot(sandbox=True, funds=5000, wait=True, risk=2.5)
print(datetime.now())
