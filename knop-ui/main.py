import func, config
from flask import Flask, request, render_template, redirect, session, flash

app = Flask(__name__)
app.secret_key = b'aw093ur9uwbtjhr9te8u9f0dgbd9gu83h'

@app.route('/')
def index():
	return render_template('knopki.html')

@app.route('/make_order_long', methods=['POST'])
def order_long():
	results = func.get_long(config.symbol, config.order_size, config.perc_prof, config.prec, config.price_round, config.do_trail, config.API_KEY, config.API_SECRET)

	flash(results[0])
	flash(results[1])

	return redirect('/')

@app.route('/make_order_short', methods=['POST'])
def order_short():
	results = func.get_short(config.symbol, config.order_size, config.perc_prof, config.prec, config.price_round, config.API_KEY, config.API_SECRET)

	flash(results[0])
	flash(results[1])

	return redirect('/')


if __name__ == "__main__":
	from waitress import serve
	serve(app, host="0.0.0.0", port=8080)