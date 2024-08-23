import func, calc
import sys, datetime

import asyncio
from lomond import WebSocket

import pandas as pd
import warnings
warnings.filterwarnings('ignore')
pd.set_option('display.max_rows', None)

STREAM = "wss://fstream.binance.com/stream"
ws = WebSocket(STREAM)

df = pd.DataFrame()
limits = 20

async def do_bot():
	print("Начали!")
	print(datetime.datetime.now())
	db_setts = func.get_setts()
	db_sett_list = func.get_sett_list(db_setts)
	df = func.get_init_data(db_sett_list)
	
	for n in range(len(df)):
		df[n] = calc.get_tema(df[n], db_sett_list[n])
		calc.check_signal(df[n], db_setts)
	
	for n in range(len(df)):
		print(df[n].tail(1))
		
####################################################################################	
	streamname = []
	for event in ws.connect():
		if event.name == "ready":
			for n in range(len(db_sett_list)):
				streamname.append(db_sett_list[n]["symbol"].lower() + "@kline_" + db_sett_list[n]["timeframe"])
			ws.send_json({"method": "SUBSCRIBE", "params": streamname, "id": 1})  #
			
		elif event.name == "text":
			data = event.json
			if 'id' in data:
				pass
			elif 'error' in data:
				print(data['error'])
			else:
				if data['data']['e'] == 'kline':
					df_1 = {}
					if data['data']['k']['x']:
						print("Получили сигнал!")
						print(datetime.datetime.now())
						df_1['time'] = datetime.datetime.fromtimestamp(data['data']['k']['t']/1000).strftime("%D %H:%M")
						df_1['symbol'] = data['data']['k']['s']
						df_1['timeframe'] = data['data']['k']['i']
						df_1['close'] = float(data['data']['k']['c'])
						
						for n in range(len(df)):
							if df_1['symbol'] + df_1['timeframe'] in df[n]['bot'][0]:
								df[n] = await func.update_data(df[n], df_1)
								df[n] = calc.get_tema(df[n], db_sett_list[n])
								print(df[n].tail(1))
								
								calc.check_signal(df[n], db_setts)
								print("Завершили цикл!")
								print(datetime.datetime.now())
								

####################################################################################
while True:
	try:
		asyncio.get_event_loop().run_until_complete(do_bot())
	except KeyboardInterrupt:
		print("Выходим!")
		sys.exit()
	except:
		print("Что-то пошло не так")
		print(sys.exc_info()[0])
		tg_message("Бот отключился.", "")
		input()
		sys.exit()