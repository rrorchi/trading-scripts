import sys, time, datetime, json
import requests
import urllib
from urllib.parse import urlencode
import urllib3.exceptions, requests.exceptions
import hmac
from lomond import WebSocket

import asyncio

import pandas as pd
import warnings
warnings.filterwarnings('ignore')
pd.set_option('display.max_rows', None)

COIN = pd.DataFrame()
in_long = False
in_short = False
entry = 0
kline_limit = 400

STREAM = "wss://fstream.binance.com/stream"
ws = WebSocket(STREAM)

#
####################################################################################

####################################################################################
# параметры

TOKEN = "1709115411:AA"			# токен телеграм-бота
CHAT = "-1001"												# id чата

KEY = "DwFR"					# ключи 
SECRET = "Eg4"			        #

ma_green = 41
ma_red = 54

order_size_o = 200						# размер ордера в монетках

symbol = 'GTCUSDT'
timeframe = '30'						# 1m, 3m, 5m, 10m и т.д.
tf_time = 'm'
streamname = 'gtcusdt@kline_30m'			# название потока
precision = 3							# кол-во знаков после запятой

#
####################################################################################

####################################################################################
def get_init_data():
	req = "https://fapi.binance.com/fapi/v1/klines?symbol=" + symbol + "&interval=" + timeframe + tf_time + "&limit=" + str(kline_limit)
	klines = requests.get(req)
	klines = klines.json()

	for n in range(0, kline_limit):
		klines[n][0] = datetime.datetime.fromtimestamp(klines[n][0]/1000).strftime("%D %H:%M")

	df = pd.DataFrame(klines[:-1], columns = ['time', 'open', 'high', 'low', 'close', '', '', '', '', '', '', ''])
	df['time'] = df['time']
	df['open'] = df['open'].astype(float)
	df['high'] = df['high'].astype(float)
	df['low'] = df['low'].astype(float)
	df['close'] = df['close'].astype(float)
	df = df.drop('', axis = 1)

	return df
######
def get_tema(df, ma_green, ma_red):
	# TEMA GREEN
	alpha = 2 / (ma_red - 1)
	df['ema_green1'] = df['close'].ewm(span = ma_green, adjust = False).mean()
	df['ema_green2'] = df['ema_green1'].ewm(span = ma_green, adjust = False).mean()
	df['ema_green3'] = df['ema_green2'].ewm(span = ma_green, adjust = False).mean()
	df['tema_green'] = round(3 * (df['ema_green1'] - df['ema_green2']) + df['ema_green3'], precision)

	# TEMA RED
	alpha = 2 / (ma_red - 1)
	df['ema_red1'] = df['close'].ewm(span = ma_red, adjust = False).mean()
	df['ema_red2'] = df['ema_red1'].ewm(span = ma_red, adjust = False).mean()
	df['ema_red3'] = df['ema_red2'].ewm(span = ma_red, adjust = False).mean()
	df['tema_red'] = round(3 * (df['ema_red1'] - df['ema_red2']) + df['ema_red3'], precision)
	
	df['signal'] = ''

	for n in range(1, kline_limit-1):
		if df['tema_green'][n-1] <= df['tema_red'][n-1] and df['tema_green'][n] > df['tema_red'][n]:
			df['signal'][n] = 'Buy!'
		if df['tema_red'][n-1] <= df['tema_green'][n-1] and df['tema_red'][n] > df['tema_green'][n]:
			df['signal'][n+1] = 'Sell!'

	return df['time'], df['tema_green'], df['tema_red'], df['close'], df['signal']
######
async def update_data(df, df_1):
	df['time'] = df['time'].shift(-1); df['time'][kline_limit-2] = df_1['time']
	df['open'] = df['open'].shift(-1); df['open'][kline_limit-2] = df_1['open']
	df['high'] = df['high'].shift(-1); df['high'][kline_limit-2] = df_1['high']
	df['low'] = df['low'].shift(-1); df['low'][kline_limit-2] = df_1['low']
	df['close'] = df['close'].shift(-1); df['close'][kline_limit-2] = df_1['close']

	df.drop([0], axis = 0)
	df.index = range(len(df.index))
	return df
######
####################################################################################

####################################################################################
# бот
async def do_bot():
# первоначальные значения для вывода
	print("Первые значения!")
	df = get_init_data()
	COIN['time'], COIN['tema_green'], COIN['tema_red'], COIN['close'], COIN['signal'] = get_tema(df, ma_green, ma_red)
	print(COIN)
	check_signal(COIN)
	
# подключаемся к потоку
	for event in ws.connect(ping_rate=600):
		if event.name == "ready":
			params = {"timestamp" : int(time.time() * 1000)}
			signature = hmac.new(SECRET.encode(), urlencode(params).encode('utf-8'), 'sha256').hexdigest()
			header = {'X-MBX-APIKEY': KEY}
			res = requests.post('https://fapi.binance.com/fapi/v1/listenKey?', params=signature, headers=header)
			results = res.json()
			print(datetime.datetime.now(), " ready ", results)
			
			ws.send_json({"method": "SUBSCRIBE", "params": [streamname, results["listenKey"]], "id": 1})  #
			
		elif event.name == "text":
			data = event.json
			if 'stream' in data and not data['stream'] == streamname:
				print("stream ", data)
			elif 'id' in data:
				print(datetime.datetime.now(), " id ", data)
			elif 'error' in data:
				print(data['error'])
			else:
				if data['data']['e'] == 'kline':
					await kline_update(df, data)
				if data['data']['e'] == 'ACCOUNT_UPDATE':
					print(data)
					await account_update(data)
				if data['data']['e'] == 'ORDER_TRADE_UPDATE':
					print(data)
					await order_update(data)
		
		elif event.name == "listenKeyExpired":
			print(data)
			params = {"timestamp" : int(time.time() * 1000)}
			signature = hmac.new(SECRET.encode(), urlencode(params).encode('utf-8'), 'sha256').hexdigest()
			header = {'X-MBX-APIKEY': KEY}
			res = requests.post('https://fapi.binance.com/fapi/v1/listenKey?', params=signature, headers=header)
			results = res.json()
			print(datetime.datetime.now(), " LK expired ", results)
			
			ws.send_json({"method": "SUBSCRIBE", "params": [streamname, results["listenKey"]], "id": 1}) #streamname, 

async def kline_update(df, data):
	df_1 = {}
	if data['stream'] == streamname:
		if data['data']['k']['x']:
			df_1['time'] = datetime.datetime.fromtimestamp(data['data']['k']['t']/1000).strftime("%D %H:%M")
			df_1['open'] = float(data['data']['k']['o'])
			df_1['high'] = float(data['data']['k']['h'])
			df_1['low'] = float(data['data']['k']['l'])
			df_1['close'] = float(data['data']['k']['c'])

			df_new = await update_data(df, df_1)
			COIN['time'], COIN['tema_green'], COIN['tema_red'], COIN['close'], COIN['signal'] = get_tema(df_new, ma_green, ma_red)
			print(COIN.tail(1))
			check_signal(COIN)
			print(datetime.datetime.now())

async def account_update(data):
	print(data['data']['a']['m'])
	print(data['data']['a']['B'])

async def order_update(data):
	print(data['data']['o']['s'], data['data']['o']['c'], data['data']['o']['S'], data['data']['o']['X'])
	
######				
def make_order(symbol, side, order_size, SECRET, KEY):
	header = {'X-MBX-APIKEY': KEY}
	params = {'symbol': symbol, 'side': side, 'type':'MARKET', 'quantity': order_size, 'timestamp': int(time.time() * 1000)}
	signature = hmac.new(SECRET.encode(), urlencode(params).encode(), 'sha256').hexdigest()
	params['signature'] = signature
	req_o = "https://fapi.binance.com/fapi/v1/order?"

	results = requests.post(req_o, params=params, headers=header)
######
def get_pos(SECRET, KEY):
	header = {'X-MBX-APIKEY': KEY}
	params = {'symbol': symbol, 'timestamp': int(time.time() * 1000)}
	signature = hmac.new(SECRET.encode(), urlencode(params).encode(), 'sha256').hexdigest()
	params['signature'] = signature
	req_o = "https://fapi.binance.com/fapi/v2/positionRisk?"

	results = requests.get(req_o, params=params, headers=header).json()
	
	entr = float(results[0]['entryPrice'])
	return(entr)
######
def tg_message(say_, _what):
	req = "https://api.telegram.org/bot" + TOKEN + "/sendMessage?chat_id="+ CHAT + "&text=" + say_ + ' ' + _what
	results = requests.get(req)
######

def check_signal(COIN):
	global in_long, in_short, entry
	last_row_i = len(COIN.index) - 1
	prev_row_i = last_row_i - 1

####################################################################################
#				расчет pnl 
	pnl = 0
	if not in_long and not in_short:
		print("PNL: ", pnl)
	if in_long:
		pnl = (COIN['close'][last_row_i] - entry) * order_size_o 
		print("PNL: ", pnl)
	if in_short:
		pnl = -(COIN['close'][last_row_i] - entry) * order_size_o
		print("PNL: ", pnl)

####################################################################################
# 			выставление ордеров

	if COIN['signal'][prev_row_i] == False and COIN['st'][last_row_i] == True:
		if not in_long and not in_short:
			print("тренд сменился вверх, покупаем")
			in_long = True
# ордер 
			make_order(symbol, 'BUY', order_size_o, SECRET, KEY)

			time.sleep(1)
			entry = get_pos(SECRET, KEY)
			to_say = symbol + " | Бот открыл лонг по "
			tg_message(to_say, str(entry))

		if not in_long and in_short:
			print("закрываем шорт, идем в лонг!")
			in_short = False
			in_long = True
# ордер 
			make_order(symbol, 'BUY', order_size_o * 2, SECRET, KEY)

			time.sleep(1)
			entry = get_pos(SECRET, KEY)
			to_say = symbol + " | Бот закрыл шорт и открыл лонг по "
			tg_message(to_say, str(entry))
			to_say = "Профит: "
			tg_message(to_say, str(pnl))

	if COIN['signal'][prev_row_i] == True and COIN['st'][last_row_i] == False:

		if not in_short and not in_long:
			print("тренд сменился вниз, продаем")
			in_short = True
# ордер
			make_order(symbol, 'SELL', order_size_o, SECRET, KEY)

			time.sleep(1)
			entry = get_pos(SECRET, KEY)
			to_say = symbol + " | Бот открыл шорт по "
			tg_message(to_say, str(entry))

		if not in_short and in_long:
			print("закрываем лонг, идем в шорт!")
			in_short = True
			in_long = False
# ордер
			make_order(symbol, 'SELL', order_size_o * 2, SECRET, KEY)

			time.sleep(1)
			entry = get_pos(SECRET, KEY)
			to_say = symbol + " | Бот закрыл лонг и открыл шорт по "
			tg_message(to_say, str(entry))
			to_say = "Профит: "
			tg_message(to_say, str(pnl))
	return		
    
####################################################################################
while True:
	try:
		asyncio.get_event_loop().run_until_complete(do_bot())
	except KeyboardInterrupt:
		print("Выходим!")
		sys.exit()
	except (urllib3.exceptions.NewConnectionError, urllib3.exceptions.MaxRetryError, requests.exceptions.ConnectionError) as e:
		print(e)
		time.sleep(10)
		pass
	except:
		print("Что-то пошло не так")
		print(sys.exc_info()[0])
		tg_message("Бот отключился.", "")
		input()
		sys.exit()