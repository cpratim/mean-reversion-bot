import time
from config import KEY_LIVE, KEY, SECRET
from polygon import PolygonRest
import json
from datetime import datetime, timedelta
import alpaca_trade_api as alpaca

client = PolygonRest(KEY_LIVE)


def read_data(f):
    with open(f, 'r') as df:
        return json.loads(df.read())

def dump_data(f, d):
    with open(f, 'w') as df:
        json.dump(d, df, indent=4)


def high_and_low(data, h_threshhold=1.5, l_threshhold=1.5, percentage=90):
    r = {}
    for t in data:
        hilc, lihc, hct, lct = 0, 0, 0, 0
        for candle in data[t]:
            v, o, c, h, l = candle
            h_p = ((h - o)/o) * 100
            l_p = ((o - l)/o) * 100
            if h_p >= h_threshhold:
                hct += 1
                if l_p >= l_threshhold: 
                    lihc += 1
            if l_p >= l_threshhold:
                lct += 1
                if h_p >= h_threshhold:
                    hilc += 1
        if lct != 0 and hct != 0:    
            a = (hilc/lct) * 100
            b = (lihc/hct) * 100
            r[t] = [a, b]
    ret = {}
    for t in r:
        if r[t][0] > percentage and r[t][1] > percentage:
            ret[t] = [r[t][0], r[t][1]]
    return ret


def high_or_low(data, h_threshhold=1.5, l_threshhold=1.5, percentage=90, min_volume=1000000):
    r = {}
    for t in data:
        h_c, l_c, ct, vs = 0, 0, 0, []
        for candle in data[t]:
            v, o, c, h, l = candle
            vs.append(v)
            h_p = ((h - o)/o) * 100
            l_p = ((o - l)/o) * 100
            if h_p >= h_threshhold: 
                h_c += 1
            if l_p >= l_threshhold: 
                l_c += 1
            ct += 1
        a = (h_c/ct) * 100
        b = (l_c/ct) * 100
        r[t] = [a, b, sum(vs)/len(vs)]
    ret = {}
    for t in r:
        if r[t][0] > percentage and r[t][1] > percentage and r[t][2] > min_volume:
            ret[t] = [r[t][0], r[t][1]]
    return ret

def find_stocks(hol, hal):
    overlap = []
    ret = {}
    for t in hol:
        if t in hal:
            overlap.append(t)
    for t in overlap:
        ret[t] = [hol[t], hal[t]]
    return ret


def _shortable(stocks):
        key_alt = 'PKXUP5PT2YHG5UXCYTYD'
        sec_alt = 'Yyn8gispxvryMmLt6oDfD5l28kFvjEPoizFp9xIc'
        client = alpaca.REST(key_alt, sec_alt, 'https://paper-api.alpaca.markets')
        s_sym = []
        for s in stocks:
            try:
                order  = client.submit_order(symbol=s, side='sell', type='market', qty=1, time_in_force='day')
                s_sym.append(s)
            except Exception as e:
                pass
        return s_sym

def check(symbols, t):
    c = []
    hal = high_and_low(client.get_all_candles(start='2020-05-03'), l_threshhold=t, h_threshhold=t)
    for s in hal:
        if s in symbols:
            c.append(s)
    return c

def get_avg(symbol, s):
    return 
    print(ah, al)

def get_symbols(risk, d=7, p=.5, s=1.5):
    now = datetime.now()
    end = str(now)[:10]
    s1 = str((now - timedelta(days=d*3)))[:10]
    s2 = str((now - timedelta(days=int(d*1.5))))[:10]
    t = p*s
    data1 = client.get_all_candles(start=s1, end=end)
    data2 = client.get_all_candles(start=s2, end=end)
    hal = high_and_low(data1, l_threshhold=t, h_threshhold=t)
    hol = high_or_low(data2, l_threshhold=t, h_threshhold=t)
    tick = find_stocks(hol, hal)
    sym = _shortable([s for s in tick])
    stocks = {}
    for s in sym:
        r = 5/risk
        av, ap, ah, al = client.get_stats(s, s=s2)
        stocks[s] = [ah/((5/r) * 100), al/((5/r) * 100), (ah/(100)), (al/(100))]
    return stocks
    