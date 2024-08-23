import requests, json, time, datetime, hmac
from urllib.parse import urlencode

callbackRate = 0.7

def get_long(symbol, order_size, perc_prof, prec, price_round, do_trail, key, secret):
	ftime = datetime.datetime.now()
    
	#results = [symbol, order_size, " BUY "] #test
	results = make_order(symbol, "BUY", order_size, secret, key, False)
	print(results)
	
	stime = datetime.datetime.now()
	
	limit_price = round(float(results[3]) + float(results[3]) * perc_prof / 100, price_round)
	limit_size = round(order_size + order_size * 0.5 / 100, prec)
    
	#results2 = [symbol, order_size, " SELL "] #test
	if do_trail:
		results2 = post_trail(symbol, "SELL", limit_size, callbackRate, secret, key, True)
	else:
		results2 = post_order(symbol, "SELL", limit_size, limit_price, secret, key, True)
	print(results2)
    
	save_log(ftime, stime, results, results2)
	return results, results2

def get_short(symbol, order_size, perc_prof, prec, price_round, do_trail, key, secret):
	ftime = datetime.datetime.now()
    
	#results = [symbol, order_size, " SELL "] #test
	results = make_order(symbol, "SELL", order_size, secret, key, False)
    print(results)
	
	stime = datetime.datetime.now()
	
	limit_price = round(float(results[3]) - float(results[3]) * perc_prof / 100, price_round)
	limit_size = round(order_size + order_size * 0.5 / 100, prec)
    
	#results2 = [symbol, order_size, " BUY "] #test
	if do_trail:
		results2 = post_trail(symbol, "BUY", limit_size, callbackRate, secret, key, True)
	else:
		results2 = post_order(symbol, "BUY", limit_size, limit_price, secret, key, True)
	print(results2)
	
	save_log(ftime, stime, results, results2)
	return results, results2
				  

def make_order(symbol, side, order_size, SECRET, KEY, close_p = False):
	header = {'X-MBX-APIKEY': KEY}
	params = {'symbol': symbol, 'side': side, 'type':'MARKET', 'quantity': order_size, 'reduceOnly': close_p, 'newOrderRespType': 'RESULT', 'timestamp': int(time.time() * 1000)}
	signature = hmac.new(SECRET.encode(), urlencode(params).encode(), 'sha256').hexdigest()
	params['signature'] = signature
	req_o = "https://fapi.binance.com/fapi/v1/order?"
	
	res = requests.post(req_o, params=params, headers=header)
	results = res.json()
	if not "code" in results:
	  results_form = [results["symbol"], results["side"],  str(order_size), results["avgPrice"]]
	else:
	  results_form = results

	return results_form

def post_order(symbol, side, order_size, limit_price, SECRET, KEY, close_p = False):
	header = {'X-MBX-APIKEY': KEY}
	params = {'symbol': symbol, 'side': side, 'type':'LIMIT', 'timeInForce': 'GTC', 'quantity': order_size, 'reduceOnly': close_p, 'price': limit_price, 'timestamp': int(time.time() * 1000)}
	signature = hmac.new(SECRET.encode(), urlencode(params).encode(), 'sha256').hexdigest()
	params['signature'] = signature
	req_o = "https://fapi.binance.com/fapi/v1/order?"
	
	res = requests.post(req_o, params=params, headers=header)
	results = res.json()
	
	if not "code" in results:
	  results_form = [results["symbol"], results["side"], str(order_size), str(limit_price)]
	else:
	  results_form = results

	return results_form

def post_trail(symbol, side, order_size, callbackRate, SECRET, KEY, close_p = False):
	header = {'X-MBX-APIKEY': KEY}
	params = {'symbol': symbol, 'side': side, 'type':'TRAILING_STOP_MARKET', 'timeInForce': 'GTC', 'quantity': order_size, 'reduceOnly': close_p, 'callbackRate': callbackRate, 'timestamp': int(time.time() * 1000)}
	signature = hmac.new(SECRET.encode(), urlencode(params).encode(), 'sha256').hexdigest()
	params['signature'] = signature
	req_o = "https://fapi.binance.com/fapi/v1/order?"
	
	res = requests.post(req_o, params=params, headers=header)
	results = res.json()
	
	if not "code" in results:
	  results_form = [results["symbol"], results["side"], str(order_size), str(results["activatePrice"])]
	else:
	  results_form = results

	return results_form


def save_log(ftime, stime, results, results2):
	time1 = str(ftime) + " | " + str(stime)
	time2 = str(stime) + " | " + str(datetime.datetime.now())

	result12 = [time1, results, time2, results2]

	with open('order_log', 'a') as file:
		json.dump(result12, file, indent = 4)