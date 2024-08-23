import os, time, datetime, json
import requests
import asyncio

import pandas as pd
import warnings
warnings.filterwarnings('ignore')
pd.set_option('display.max_rows', None)

limits = 20

def get_setts():
	db_setts = {}
	for filename in os.listdir(os.path.join(os.getcwd(), "users")):
		with open(os.path.join(os.getcwd(), "users", filename), 'r') as f:
			users_data = json.load(f)
			db_setts[users_data["username"]] = users_data

	return db_setts

def get_sett_list(db_setts):
	db_sett_list = []
	for n in db_setts:
		for m in db_setts[n]["bots"]:
			data = {}
			# data["user"] = n
			data["symbol"] = m["symbol"]
			data["timeframe"] = m["timeframe"]
			data["tema_fast"] = m["tema_fast"]
			data["tema_slow"] = m["tema_slow"]
			data["prec"] = m["prec"]
			
			if data not in db_sett_list:
				db_sett_list.append(data)
			
	for n in db_sett_list:
		print(n)
	return db_sett_list

def write_setts(user, symbol, timeframe, side):
	users_data = {}
	with open(os.path.join(os.getcwd(), "users", user), 'r') as f:
		users_data = json.load(f)
		for n in range(len(users_data["bots"])):
			if symbol == users_data["bots"][n]["symbol"] and timeframe == users_data["bots"][n]["timeframe"]:
				users_data["bots"][n]["in_pos"] = side	
				print(users_data["bots"][n])
				
	with open(os.path.join(os.getcwd(), "users", user), 'w') as f:
		json.dump(users_data, f, indent = 2)	
		

def get_init_data(db_sett_list):
	df = []
	for bot in db_sett_list:
		req = "https://fapi.binance.com/fapi/v1/klines?symbol=" + bot["symbol"] + "&interval=" + bot["timeframe"] + "&limit=" + str(limits)
		klines = requests.get(req)
		klines = klines.json()
		
		for n in range(0, limits):
			klines[n][0] = datetime.datetime.fromtimestamp(klines[n][0]/1000).strftime("%D %H:%M")

		data = pd.DataFrame(klines[:-1], columns = ['time', '', '', '', 'close', '', '', '', '', '', '', ''])
		data.insert(0,'bot', value=bot["symbol"] + bot["timeframe"])
		data['time'] = data['time']
		data['close'] = data['close'].astype(float)
		data = data.drop('', axis = 1)
		df.append(data)
	print("Взяли данные!")
	print(datetime.datetime.now())
	return df

async def update_data(df, df_1):
	df['bot'] = df['bot'].shift(-1); df['bot'][limits-2] = df_1['symbol'] + df_1['timeframe']
	df['time'] = df['time'].shift(-1); df['time'][limits-2] = df_1['time']
	df['close'] = df['close'].shift(-1); df['close'][limits-2] = df_1['close']

	df.drop([0], axis = 0)
	df.index = range(len(df.index))

	return df

def get_pos_percent(prec, pos, current_price, leverage):
    order_size = round(int(pos) / current_price * int(leverage), int(prec))
    return order_size

def make_order(user, symbol, side, order_size, SECRET, KEY, reduce):
	header = {'X-MBX-APIKEY': KEY}
	params = {'symbol': symbol, 'side': side, 'type':'MARKET', 'quantity': order_size, 'reduceOnly': reduce, 'newOrderRespType': 'RESULT', 'timestamp': int(time.time() * 1000)}
	signature = hmac.new(SECRET.encode(), urlencode(params).encode(), 'sha256').hexdigest()
	params['signature'] = signature
	req_o = "https://fapi.binance.com/fapi/v1/order?"

	res = requests.post(req_o, params=params, headers=header)
	results = res.json()
	if not "code" in results:
	  results_form = user + ": " + results["symbol"] + " " + results["side"] + " " + str(order_size)  + " | " + results["avgPrice"]
	else:
	  results_form = results
	print(results)

	return results_form

def tg_message(message, TOKEN, CHAT):
	print("Отправили сообщение!")
	print(datetime.datetime.now())
	req = "https://api.telegram.org/bot" + TOKEN + "/sendMessage?chat_id="+ CHAT + "&text=" + message
	results = requests.get(req)