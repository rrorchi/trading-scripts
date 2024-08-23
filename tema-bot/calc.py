import func, datetime
import pandas as pd

def get_tema(df, setts):
	data = pd.DataFrame()
	ma_green = int(setts["tema_fast"])
	ma_red = int(setts["tema_slow"])
	precision = int(setts["prec"])

	# TEMA GREEN
	data['ema_green1'] = df['close'].ewm(span = ma_green, adjust = False).mean()
	data['ema_green2'] = data['ema_green1'].ewm(span = ma_green, adjust = False).mean()
	data['ema_green3'] = data['ema_green2'].ewm(span = ma_green, adjust = False).mean()
	df['tema_green'] = round(3 * (data['ema_green1'] - data['ema_green2']) + data['ema_green3'], precision)

	# TEMA RED
	data['ema_red1'] = df['close'].ewm(span = ma_red, adjust = False).mean()
	data['ema_red2'] = data['ema_red1'].ewm(span = ma_red, adjust = False).mean()
	data['ema_red3'] = data['ema_red2'].ewm(span = ma_red, adjust = False).mean()
	df['tema_red'] = round(3 * (data['ema_red1'] - data['ema_red2']) + data['ema_red3'], precision)
	
	df['signal'] = ''

	for m in range(1, len(df["close"])):
		if df['tema_green'][m-1] <= df['tema_red'][m-1] and df['tema_green'][m] > df['tema_red'][m]:
			df['signal'][m] = 'Buy!'
		if df['tema_green'][m-1] >= df['tema_red'][m-1] and df['tema_green'][m] < df['tema_red'][m]:
			df['signal'][m+1] = 'Sell!'
	
	print("Рассчитали ТЕМА!")
	print(datetime.datetime.now())
	return df #df['bot'], df['time'], df['close'], df['tema_green'], df['tema_red'], df['signal']

def check_signal(df, db):

	last_row_i = len(df.index) - 1
	prev_row_i = last_row_i - 1
	results = ""

############ long
	if df['signal'][last_row_i] == "Buy!":
		for n in db:
			for m in db[n]["bots"]:
				if df['bot'][last_row_i] == m['symbol'] + m['timeframe']:
					msg = "TEMA: Long!" + "\r\n"
					order_size = func.get_pos_percent(m["min_dig"], m["qty_pos"], df['close'][last_row_i], m["leverage"])
					if m['in_pos'] == 'No':
						results = msg + func.make_order(db[n]["username"], m["symbol"], "BUY", order_size, db[n]["key2"], db[n]["key1"], False)
					if m['in_pos'] != 'SELL':
						####### закрытие
						results = func.make_order(db[n]["username"], m["symbol"], "SELL", order_size, db[n]["key2"], db[n]["key1"], True)
						####### заход
						results = msg + results + "\r\n" + func.make_order(db[n]["username"], m["symbol"], "BUY", order_size, db[n]["key2"], db[n]["key1"], False)
					print(results)
					func.tg_message(results, db[n]["tg_token"], db[n]["chat_id"])
					func.write_setts(db[n]["username"], m["symbol"], m['timeframe'], "BUY")

############ short 
	if df['signal'][last_row_i] == "Sell!":
		for n in db:
			for m in db[n]["bots"]:
				if df['bot'][last_row_i] == m['symbol'] + m['timeframe']:
					msg = "TEMA: Short!" + "\r\n"
					order_size = func.get_pos_percent(m["min_dig"], m["qty_pos"], df['close'][last_row_i], m["leverage"])
					if m['in_pos'] == 'No':
						results = msg + func.make_order(db[n]["username"], m["symbol"], "SELL", order_size, db[n]["key2"], db[n]["key1"], False)
					if m['in_pos'] == 'BUY':
						####### закрытие
						results = func.make_order(db[n]["username"], m["symbol"], "BUY", order_size, db[n]["key2"], db[n]["key1"], True)
						####### заход
						results = msg + results + "\r\n" + func.make_order(db[n]["username"], m["symbol"], "SELL", order_size, db[n]["key2"], db[n]["key1"], False)
					print(results)
					func.tg_message(results, db[n]["tg_token"], db[n]["chat_id"])
					func.write_setts(db[n]["username"], m["symbol"], m['timeframe'], "SELL")
		