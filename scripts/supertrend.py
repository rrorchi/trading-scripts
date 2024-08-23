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
kline_limit = 500

STREAM = "wss://fstream.binance.com/stream"
ws = WebSocket(STREAM)

#
####################################################################################

####################################################################################
# параметры

TOKEN = "1709115411:AAFhWG"			# токен телеграм-бота
CHAT = "-1001"												# id чата

KEY = 'gf0S'				# ключи
SECRET =  'Mpi51'			#

atr_length = 20							# период
multiplier = 5							# фактор

order_size_o = 200						# размер ордера в монетках

symbol = 'GTCUSDT'
timeframe = '30m'						# 1m, 3m, 5m, 10m и т.д.
streamname = 'belusdt@kline_1m'			# название потока
precision = 4							# кол-во знаков после запятой

#
####################################################################################

####################################################################################
# расчет значений
def get_init_data():
	req = "https://fapi.binance.com/fapi/v1/klines?symbol=" + symbol + "&interval=" + timeframe + "&limit=" + str(kline_limit)
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
def get_supertrend(df, atr_length, multiplier, trend):
	# ATR
	df['h_l'] = df['high'] - df['low']
	df['h_pc'] = abs(df['high'] - df['close'].shift(1))
	df['l_pc'] = abs(df['low'] - df['close'].shift(1))

	df['tr'] = df[['h_l', 'h_pc', 'l_pc']].max(axis = 1)

	# df = df.sort_index()
	df['atr'] = df['tr'].ewm(alpha = 1 / atr_length, adjust = False).mean()

	# H/L AVG AND BASIC UPPER & LOWER BAND
	df['upper_band'] = float('nan')
	df['lower_band'] = float('nan')
	for n in range(0, kline_limit-1):
		df['upper_band'][n] = round(abs((((df['high'][n] + df['low'][n]) / 2) + multiplier * df['atr'][n])), precision)
		df['lower_band'][n] = round(abs((((df['high'][n] + df['low'][n]) / 2) - multiplier * df['atr'][n])), precision)

	df['in_uptrend'] = trend	# передать предыдущее значение СТ
	df['upt'] = float('nan')
	df['dt'] = float('nan')

	for curr in range(1, len(df.index)):
		prev = curr - 1

# если закрытие сейчас > предыдущ значения красной - мы идем вверх
		if df['close'][curr] >= df['dt'][prev]:
			df['in_uptrend'][curr] = True
			if df['lower_band'][curr] < df['lower_band'][prev]:
				df['upt'][curr] = df['lower_band'][curr]
			else:
				df['upt'][curr] = df['lower_band'][curr]
			df['dt'][curr] = float('nan')

# если закрытие сейчас < предыдущ значения зеленой - мы идем вниз
		elif df['close'][curr] <= df['upt'][prev]:
			df['in_uptrend'][curr] = False
			if df['upper_band'][curr] > df['upper_band'][prev]:
				df['dt'][curr] = df['upper_band'][curr]
			else:
				df['dt'][curr] = df['upper_band'][curr]
			df['upt'][curr] = float('nan')


# если в аптренде - то показывай лоубенд - или следующий не меньший или тот же
		elif df['close'][curr] > df['lower_band'][curr] and df['in_uptrend'][prev]:
			if df['lower_band'][curr] < df['lower_band'][prev]:
				df['lower_band'][curr] = df['lower_band'][prev]
			if df['upper_band'][curr] > df['upper_band'][prev]:
				df['upper_band'][curr] = df['upper_band'][prev]
			df['in_uptrend'][curr] = True
			df['upt'][curr] = df['lower_band'][curr]
			if df['upt'][curr] < df['upt'][prev]:
				df['upt'][curr] = df['upt'][prev]

# # если в даунтренде - то показывай апбенд - или следующий не больший или тот же
		elif df['close'][curr] < df['upper_band'][curr] and not df['in_uptrend'][prev]:
			if df['lower_band'][curr] < df['lower_band'][prev]:
				df['lower_band'][curr] = df['lower_band'][prev]
			if df['upper_band'][curr] > df['upper_band'][prev]:
				df['upper_band'][curr] = df['upper_band'][prev]
			df['in_uptrend'][curr] = False
			df['dt'][curr] = df['upper_band'][curr]
			if df['dt'][curr] > df['dt'][prev]:
				df['dt'][curr] = df['dt'][prev]

	return df['time'], df['in_uptrend'], df['upt'], df['dt'], df['lower_band'], df['upper_band'], df['close']
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
	COIN['time'], COIN['st'], COIN['st_upt'], COIN['st_dt'], COIN['low_b'], COIN['up_b'], COIN['close'] = get_supertrend(df, atr_length, multiplier, True)
	print(COIN.tail(10))
	check_signal(COIN)

# подключаемся к потоку
	for event in ws:
		if event.name == "ready":
			ws.send_json({"method": "SUBSCRIBE", "params": [streamname], "id": 1})
		elif event.name == "text":

			data = event.json
			if 'id' in data:
				pass
			elif 'error' in data:
				print(data['error'])
			else:
				if data['data']['e'] == 'kline':
					df_1 = {}
					if data['stream'] == streamname:
						if data['data']['k']['x']:
							df_1['time'] = datetime.datetime.fromtimestamp(data['data']['k']['t']/1000).strftime("%D %H:%M")
							df_1['open'] = float(data['data']['k']['o'])
							df_1['high'] = float(data['data']['k']['h'])
							df_1['low'] = float(data['data']['k']['l'])
							df_1['close'] = float(data['data']['k']['c'])

							df_new = await update_data(df, df_1)
							trend = COIN['st'][kline_limit-2]
							COIN['time'], COIN['st'], COIN['st_upt'], COIN['st_dt'], COIN['low_b'], COIN['up_b'], COIN['close'] = get_supertrend(df_new, atr_length, multiplier, trend)
							print(COIN.tail(10))
							check_signal(COIN)
							print(datetime.datetime.now())
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

	if COIN['st'][prev_row_i] == False and COIN['st'][last_row_i] == True:
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

	if COIN['st'][prev_row_i] == True and COIN['st'][last_row_i] == False:

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