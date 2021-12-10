from flask import Flask, render_template, redirect, url_for, request, send_file, flash, session
import requests as req
import os
import logging
from io import BytesIO
import qrcode

app = Flask(__name__)
app.secret_key = b'joinmarket-gui'

API_IP = "localhost"
API_PORT = 28183
API_URL = "https://" + API_IP + ":" + str(API_PORT) + "/api/v1"

MINSIZE = 100000

def get_token():
	return session['token']

def set_token(token):
	session['token'] = token

def delete_token():
	session.pop('token', None)

def comma_seperated_sats(balance):
	balance_str = str(balance)
	ans = ''
	for i in range(0,len(balance_str)):
		ans += balance_str[len(balance_str)-i-1]
		if i%3==2 and i<len(balance_str)-1:
			ans += ','
	return ans[::-1]

def generate_qr_code(url):
	qr = qrcode.QRCode(
		version=2,
		error_correction=qrcode.constants.ERROR_CORRECT_H,
		box_size=10,
		border=4)

	qr.add_data(url)
	qr.make(fit=True)
	img = qr.make_image()
	return img

def getSetting(section, field):
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	url = API_URL + '/wallet/' + walletName + '/configget'
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	configJSON = {'section': section, 'field': field}
	r = req.post(url, json=configJSON, headers=authHeader, verify=False)
	return r.json()['configvalue']

def setSettings(form):
	for entry, value in form.items():
		# app.logger.info('Entry: %s, value: %s', entry, value)
		section, field = entry.split('.')
		r = req.get(API_URL + '/session', verify=False).json()
		walletName = r['wallet_name']

		authHeader = {'Authorization': 'Bearer ' + get_token()}

		settingsJSON = {
			'section': section,
			'field': field,
			'value': value
		}
		r = req.post(API_URL + '/wallet/'+walletName+'/configset', json=settingsJSON, headers=authHeader, verify=False)


@app.route("/")
def index_page():
	try:
		r = req.get(API_URL + '/session', verify=False).json()
		if r['wallet_name'] == "None":
			return redirect(url_for('unlock'))
		else:
			return redirect(url_for('balance'))
	except:
		templateData = {
			"error": "Can't connect to Joinmarket backend. Check " + API_IP
		}
		return render_template('error.html', **templateData)


@app.route("/unlock", methods=['GET', 'POST'])
def unlock():
	if request.method == 'GET':
		try:
			# get list of wallets from Joinmarket
			r = req.get(API_URL + '/wallet/all', verify=False)
			listWallets = r.json()['wallets']
			if listWallets == []:
				return redirect(url_for('create'))
			# prepare template data dictionary
			templateData = {
				'wallet_unlocked': False,
				'wallets': listWallets
			}
			# render unlock page with list of wallets in <select>
			return render_template('unlock.html', **templateData)
		except:
			templateData = {
				"error": "Can't connect to Joinmarket backend. Check " + API_IP
			}
			return render_template('error.html', **templateData)
	else:
		# POST request to unlock wallet
		walletName = request.form['walletname']
		passwordJSON = {'password': request.form['password']}
		r = req.post(API_URL + '/wallet/' + walletName + '/unlock', json=passwordJSON, verify=False)
		if r.status_code == 200:
			# save the TOKEN
			set_token(r.json()['token'])
			# confirm the session is unlocked
			r = req.get(API_URL + '/session', verify=False).json()
			assert(walletName == r['wallet_name'])
			# flash success alert
			flash("Wallet unlocked successfully!", category="success")
			# redirect to balance page
			return redirect(url_for('balance'))
		else:
			flash("Error unlocking! Check password.", category="danger")
			return redirect(url_for('unlock'))

@app.route("/create", methods=['GET', 'POST'])
def create():
	if request.method == 'GET':
		return render_template('create.html')
	else: # handle POST request
		walletJSON = {
			'walletname': request.form['walletname'],
			'password': request.form['password'],
			'wallettype': request.form['wallettype']
		}
		r = req.post(API_URL + '/wallet/create', json=walletJSON, verify=False)
		if r.status_code == 200:
			token = r.json()['token']
			set_token(token)
			flash("Wallet created successfully!", category="success")
			return redirect(url_for('balance'))

@app.route("/balance")
def balance():
	try:
		r = req.get(API_URL + '/session', verify=False).json()
		walletName = r['wallet_name']
		makerRunning = r['maker_running']
		coinjoinRunning = r['coinjoin_in_process']

		authHeader = {'Authorization': 'Bearer ' + get_token()}
		r = req.get(API_URL + '/wallet/'+walletName+'/display', headers=authHeader, verify=False)

		if r.status_code == 200:
			walletInfo = r.json()['walletinfo']
			total_balance_sats = round(float(walletInfo['total_balance'])*1e8)
			mixdepth_balance_sats = []
			for i in range(5):
				balance = comma_seperated_sats(round(float(walletInfo['accounts'][i]['account_balance'])*1e8))
				mixdepth_balance_sats.append(balance)
			templateData = {
				'wallet_unlocked': True,
				'total_balance_sats': comma_seperated_sats(total_balance_sats),
				'mixdepth_balance_sats': mixdepth_balance_sats,
				'sufficient_balance_yg': total_balance_sats >= MINSIZE,
				'yg_running': makerRunning,
				'coinjoin_running': coinjoinRunning,
			}
			return render_template('balance.html', **templateData)
		else:
			return r.json()
	except:
		templateData = {
			"error": "Can't connect to Joinmarket backend. Check " + API_IP
		}
		return render_template('error.html', **templateData)

@app.route("/lock")
def lock():
	try:
		r = req.get(API_URL + '/session', verify=False).json()
		walletName = r['wallet_name']
		authHeader = {'Authorization': 'Bearer ' + get_token()}
		r = req.get(API_URL + '/wallet/'+walletName+'/lock', headers=authHeader, verify=False)
		if r.status_code == 200:
			delete_token()
			flash('Wallet locked!', category="success")
			return redirect(url_for('unlock'))
		else:
			return redirect(url_for('balance'))
	except:
		templateData = {
			"error": "Can't connect to Joinmarket backend. Check " + API_IP
		}
		return render_template('error.html', **templateData)

@app.route("/deposit")
def deposit(address=None):
	if address == None:
		r = req.get(API_URL + '/session', verify=False).json()
		walletName = r['wallet_name']
		authHeader = {'Authorization': 'Bearer ' + get_token()}
		r = req.get(API_URL + '/wallet/'+walletName+'/address/new/0', headers=authHeader, verify=False)

		if r.status_code == 200:
			templateData = {
				'wallet_unlocked': True,
				'address': r.json()['address']
			}
			return render_template('deposit.html', **templateData)
		else:
			return r.json()
	else:
		templateData = {
			'address': address
		}
		return render_template('deposit.html', **templateData)

@app.route("/withdraw", methods=['GET', 'POST'])
def withdraw():
	if request.method == 'GET':
		templateData = {
			'wallet_unlocked': True
		}
		return render_template('withdraw.html', **templateData)
	else:
		r = req.get(API_URL + '/session', verify=False).json()
		walletName = r['wallet_name']

		authHeader = {'Authorization': 'Bearer ' + get_token()}
		url = API_URL + '/wallet/'+walletName+'/taker/direct-send'
		r = req.post(url, headers=authHeader, json=request.form, verify=False)
		if r.status_code == 200:
			flash("Funds withdrawn successfully!", category="success")
			return redirect(url_for("balance"))
		else:
			flash("Error withdrawing funds. Error code: " + str(r.status_code), category="danger")
			return render_template("withdraw.html")


@app.route("/yg")
def yg():
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	makerRunning = r['maker_running']

	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(API_URL + '/wallet/'+walletName+'/display', headers=authHeader, verify=False)
	if r.status_code == 200:
		walletInfo = r.json()['walletinfo']
		total_balance_sats = round(float(walletInfo['total_balance'])*1e8)
		fb_sats = 0
		try:
			fb_sats = round(float(walletInfo['accounts'][0]['branches'][2]['balance'])*1e8)
		except:
			pass

	templateData = {
		'wallet_unlocked': True,
		'fb_sats': comma_seperated_sats(fb_sats),
		'fb_exists': fb_sats > 0,
		'yg_running': makerRunning
	}
	return render_template('yg.html', **templateData)

@app.route("/getfbaddress", methods=['POST'])
def getfbaddress():
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	lockDate = request.form['lockdate-year'] + '-' + request.form['lockdate-month']
	url = API_URL + '/wallet/' + walletName + '/address/timelock/new/' + lockDate
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(url, headers=authHeader, verify=False)
	if r.status_code == 200:
		address = r.json()['address']
		return deposit(address)
	else:
		templateData = {
			"error": "Can't create Fidelity bond. Error code:" + str(r.status_code)
		}
		return render_template('error.html', **templateData)

@app.route("/start-yg", methods=['POST'])
def startYG():
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	url = API_URL + '/wallet/' + walletName + '/maker/start'
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	ygConfig = {
		'txfee': 0,
		'cjfee_r': str(float(request.form['cjfee_r'])/100),
		'cjfee_a': 0,
		'ordertype': 'reloffer',
		'minsize': MINSIZE

	}
	r = req.post(url, headers=authHeader, json=ygConfig, verify=False)
	flash('Maker started successfully!', category="success")
	return redirect(url_for('balance'))

@app.route("/stop-yg")
def stopYG():
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	url = API_URL + '/wallet/' + walletName + '/maker/stop'
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(url, headers=authHeader, verify=False)
	flash('Maker stopped successfully!', category="success")
	return redirect(url_for('balance'))

@app.route("/coinjoin", methods=['GET', 'POST'])
def coinjoin():
	if request.method == 'GET':
		templateData = {
			'wallet_unlocked': True,	
		}
		return render_template('coinjoin.html', **templateData)
	else:
		r = req.get(API_URL + '/session', verify=False).json()
		walletName = r['wallet_name']

		authHeader = {'Authorization': 'Bearer ' + get_token()}
		url = API_URL + '/wallet/'+walletName+'/taker/coinjoin'
		r = req.post(url, headers=authHeader, json=request.form, verify=False)
		if r.status_code == 200:
			flash("Coinjoin submitted successfully!", category="success")
			return redirect(url_for("balance"))
		else:
			return r.json()

@app.route("/about")
def about():
	return render_template("about.html")

@app.route("/get_qr_code")
def get_qr_code():
	url = request.args.get('url')
	img_buf = BytesIO()
	img = generate_qr_code(url)
	img.save(img_buf)
	img_buf.seek(0)
	return send_file(img_buf, mimetype='image/png')

@app.route("/settings", methods=['GET', 'POST'])
def settings():
	settingsDict = {
		# 'DAEMON': ['no_daemon', 'daemon_port', 'daemon_host', 'use_ssl'],
		'BLOCKCHAIN': ['rpc_host', 'rpc_port', 'rpc_user', 'rpc_password', 'rpc_wallet_file'],
		'POLICY': ['tx_fees']
	}
	settingsData = {}
	if request.method == 'GET':
		# populate settingsData dictionary
		for section, fields in settingsDict.items():
			settingsData[section] = {}
			for field in fields:
				settingsData[section][field] = getSetting(section, field)
	else: # POST request method
		setSettings(request.form)
		for section, fields in settingsDict.items():
			settingsData[section] = {}
			for field in fields:
				settingsData[section][field] = getSetting(section, field)
	return render_template('settings.html', **settingsData)

if __name__ == "__main__":
	app.run(host='0.0.0.0', port=5002)
