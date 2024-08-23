import sys, time, datetime, json

import requests
import urllib
from urllib.parse import urlencode
import hmac
from lomond import WebSocket

import asyncio

import pandas as pd
import warnings
warnings.filterwarnings('ignore')
pd.set_option('display.max_rows', None)

global in_long, in_short
in_long = False
in_short = False
entry = 0
kline_limit = 500

STREAM = "wss://fstream.binance.com/stream"
ws = WebSocket(STREAM)

COIN = pd.DataFrame()

#
####################################################################################

####################################################################################
# параметры

TOKEN = "1709115411:AAFh"			# токен телеграм-бота
CHAT = "-1007"												# id чата

KEY = "bHI"				# ключи из конфига
SECRET = "V1Ur"		#

length = 14								# период
overBought = 71							
overSold = 25

order_size_o = 200						# размер ордера в монетках

symbol = 'NKNUSDT'
timeframe = '1m'						# 1m, 3m, 5m, 10m и т.д.
streamname = 'nknusdt@kline_1m'			# название потока
precision = 5							# кол-во знаков после запятой

#
####################################################################################

####################################################################################
###### 
def get_data():
	req = "https://fapi.binance.com/fapi/v1/klines?symbol=" + symbol + "&interval=" + timeframe + "&limit=" + str(kline_limit)
	klines = requests.get(req)
	klines = klines.json()

	for n in range(0, kline_limit):
		klines[n][0] = datetime.datetime.fromtimestamp(klines[n][0]/1000).strftime("%D %H:%M")

	df = pd.DataFrame(klines[:-1], columns = ['time', '', '', '', 'close', '', '', '', '', '', '', ''])
	df['time'] = df['time']
	df['close'] = df['close'].astype(float)
	df = df.drop('', axis = 1)

	return df
######
def get_rsi(df, length, precision):
	df['change'] = (df['close'] - df['close'].shift(1))
	df['up'] = 0.0
	df['down'] = 0.0
	for n in range(length-1, kline_limit-1):
		df['up'][n] = max(df['change'][n], 0)
		df['down'][n] = min(df['change'][n], 0) * -1

	df['avgUp'] = df['up'].ewm(alpha = 1/length, adjust = False).mean()
	df['avgDown'] = df['down'].ewm(alpha = 1/length, adjust = False).mean()
	df['rs'] = round(df['avgUp'] / df['avgDown'], precision)
	df['rsi'] = round(100 - (100 / (1 + df['rs'])), precision)

	df['signal'] = ''

	for n in range(length-1, kline_limit-1):
		if df['rsi'][n-1] < overSold and df['rsi'][n] > overSold:
			df['signal'][n] = 'Buy!'
		if df['rsi'][n-1] > overBought and df['rsi'][n] < overBought:
			df['signal'][n+1] = 'Sell!'

	return df['time'], df['close'], df['rsi'], df['signal']
######
async def update_data(df, df_1):
	df['time'] = df['time'].shift(-1); df['time'][kline_limit-2] = df_1['time']
	df['close'] = df['close'].shift(-1); df['close'][kline_limit-2] = df_1['close']

	df.drop([0], axis = 0)
	df.index = range(len(df.index))
	return df
####################################################################################
# бот
async def do_bot():
	df = get_data()
	COIN['time'], COIN['close'], COIN['RSI'], COIN['signal'] = get_rsi(df, length, precision)
	print(COIN)

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
							df_1['close'] = float(data['data']['k']['c'])

							df_new = await update_data(df, df_1)
							COIN['time'], COIN['close'], COIN['RSI'], COIN['signal'] = get_rsi(df_new, length, precision)
							print(COIN.tail(20))
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

	print("СДЕЛКА: ", symbol, side, order_size)
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
	print(say_, _what)
######
####################################################################################

####################################################################################
#
def check_signal(COIN):
	global in_long, in_short, entry
	last_row_i = len(COIN.index) - 1
	prev_row_i = last_row_i - 1

####################################################################################
#				расчет pnl и стопов
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

	if COIN['RSI'][prev_row_i] < overSold and COIN['RSI'][last_row_i] > overSold:

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

		if in_long:
			print("Уже в лонге!")

	if COIN['RSI'][prev_row_i] > overBought and COIN['RSI'][last_row_i] < overBought:

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

		if in_short:
			print("Уже в шорте!")
            
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