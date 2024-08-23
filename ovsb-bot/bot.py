import json, datetime, time
import threading, signal, sys
from queue import Queue

import requests
from lomond import WebSocket

# канал в ТГ
TOKEN = "1760087170:AA" 
CHAT = "-10"

# стрим данных
websocket = WebSocket('wss://fstream.binance.com/ws/dogeusdt@aggTrade')

# настройки блока
block_size = 50000000
price_min_s = 1000000; price_max_s = 0; price_min_b = 1000000; price_max_b = 0
qtt_s = 0; j_s = 0; qtt_b = 0; j_b = 0
side = ''

def get_data(qu):
	for event in websocket:
		try:
			if event.name == "ready":
				websocket.send_json(type='subscribe')
			elif event.name == "text":

				data = event.json
				taker_seller = data['m']; 	price_r = float(data['p']); 	qtty_r = float(data['q'])
				print('Received data: ','	', 'side: ', taker_seller, 'qtty: ', "{0:.5f}".format(qtty_r), 'price: ', "{0:.2f}".format(price_r))

				evt = threading.Event()
				qu.put((data, evt))
				evt.wait()

		except KeyError:
			pass
		except KeyboardInterrupt:
			stopper()


def enroute(qu):
	while True:
		try:
			data, evt = qu.get()

			taker_seller = data['m']
			price_r = float(data['p'])
			qtty_r = float(data['q'])

			if taker_seller:
				data_to_send = sell_block(price_r, qtty_r)

			if not taker_seller:
				data_to_send = buy_block(price_r, qtty_r)

			if data_to_send[3] >= block_size:
				to_send = process_to_send(data_to_send)
				
				s_evt = threading.Event()
				send_qu.put((to_send, s_evt))
				send_processed(send_qu)

			evt.set()
			qu.task_done()

		except KeyboardInterrupt:
			stopper()

def sell_block(price, qtty):
	global price_min_s; global price_max_s; global qtt_s
	side = 'sell'

	if price < price_min_s:
		price_min_s = price
	if price > price_max_s:
		price_max_s = price

	qtt_s += qtty

	print('Processed data: ', '	', 'side: ', side, 'qtty: ', "{0:.5f}".format(qtt_s), 'min: ', "{0:.2f}".format(price_min_s), 'max: ', "{0:.2f}".format(price_max_s))

	return(side, price_min_s, price_max_s, qtt_s)

def buy_block(price, qtty):
	global price_min_b; global price_max_b; global qtt_b
	side = 'buy'

	if price < price_min_b:
		price_min_b = price
	if price > price_max_b:
		price_max_b = price

	qtt_b += qtty

	print('Processed data: ', '	', 'side: ', side, 'qtty: ', "{0:.5f}".format(qtt_b), 'min: ', "{0:.2f}".format(price_min_b), 'max: ', "{0:.2f}".format(price_max_b))

	return(side, price_min_b, price_max_b, qtt_b)

def process_to_send(data_to_send):
	global price_min_s; global price_max_s; global qtt_s
	global price_min_b; global price_max_b; global qtt_b
	global j_s; global j_b;

	if data_to_send[0] == 'sell':
		price_min_s = 1000000
		price_max_s = 0
		qtt_s = 0
		j_s += 1
		print('Sent data!', '	', '	', 'side: ', data_to_send[0], 'price min: ', "{0:.5f}".format(data_to_send[1]), 'price max: ', "{0:.5f}".format(data_to_send[2]), 'block №: ', j_s)

		msg_to_send = ("🌵 buy: %s  \r\nmax: %s \r\nmin: %s" % (j_s, "{0:.6f}".format(data_to_send[2]), "{0:.6f}".format(data_to_send[1])))

		return(msg_to_send)

	if data_to_send[0] == 'buy':
		price_min_b = 1000000
		price_max_b = 0
		qtt_b = 0
		j_b += 1
		print('Sent data!', '	', '	', 'side: ', data_to_send[0], 'price min: ', "{0:.5f}".format(data_to_send[1]), 'price max: ', "{0:.5f}".format(data_to_send[2]), 'block №: ', j_b)

		msg_to_send = ("🍄 sell: %s  \r\nmax: %s \r\nmin: %s" % (j_b, "{0:.6f}".format(data_to_send[2]), "{0:.6f}".format(data_to_send[1])))

		return(msg_to_send)

def send_processed(send_qu):
	q_to_send, s_evt = send_qu.get()

	req = "https://api.telegram.org/bot" + TOKEN + "/sendMessage?chat_id="+ CHAT + "&text=" + q_to_send
	results = requests.get(req)

	s_evt.set()
	send_qu.task_done()

def stopper():
	thread_two.stop()
	thread_one.stop()
	sys.exit('Exiting...')

def main():
	qu = Queue()
	send_qu = Queue()

	thread_one = threading.Thread(target=get_data, args=(qu,))
	thread_two = threading.Thread(target=enroute, args=(qu,))

	thread_one.start()
	thread_two.start()

	qu.join()


if __name__ == '__main__':
	main()