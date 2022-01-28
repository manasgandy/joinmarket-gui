import logging
from flask import Flask, render_template, redirect, url_for, request, send_file, flash, session
from flask import current_app as app
import requests as req
import os
import logging
from io import BytesIO
import qrcode
from .service import JoinmarketguiService

logger = logging.getLogger(__name__)

joinmarketgui_endpoint = JoinmarketguiService.blueprint

app.secret_key = b'joinmarket-gui'

try:
	API_IP = os.environ['JM_WALLET_IP']
except:
	API_IP = 'localhost'

try:
	CERT = os.environ['SSL_CERT']
except:
	CERT = False

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
	r = req.get(API_URL + '/session', verify=CERT).json()
	walletName = r['wallet_name']
	url = API_URL + '/wallet/' + walletName + '/configget'
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	configJSON = {'section': section, 'field': field}
	r = req.post(url, json=configJSON, headers=authHeader, verify=CERT)
	return r.json()['configvalue']

def setSettings(form):
	for entry, value in form.items():
		# app.logger.info('Entry: %s, value: %s', entry, value)
		section, field = entry.split('.')
		r = req.get(API_URL + '/session', verify=CERT).json()
		walletName = r['wallet_name']

		authHeader = {'Authorization': 'Bearer ' + get_token()}

		settingsJSON = {
			'section': section,
			'field': field,
			'value': value
		}
		r = req.post(API_URL + '/wallet/'+walletName+'/configset', json=settingsJSON, headers=authHeader, verify=CERT)

def is_backend_down():
	try:
		r = req.get(API_URL + '/wallet/all', verify=CERT)
		return r.status_code != 200
	except:
		return True


def is_wallet_locked():
	r = req.get(API_URL + '/session', verify=CERT).json()
	return r['wallet_name'] == 'None'

def is_token_present():
	try:
		# app.logger.info(session['token'])
		return session['token'] != None
	except:
		return False

@joinmarketgui_endpoint.route("/")
def index():
	return render_template('layout_embedded.html')

@joinmarketgui_endpoint.route("/index")
def index_pure():
	logger.error("------------------backend down on API_URL "+API_URL)
	if is_backend_down():
		return render_template('error.html')
	
	if is_wallet_locked():
		return redirect(url_for('joinmarketgui_endpoint.unlock'))
	elif is_token_present():
		return redirect(url_for('joinmarketgui_endpoint.balance'))
	else:
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)


@joinmarketgui_endpoint.route("/unlock", methods=['GET', 'POST'])
@app.csrf.exempt
def unlock():
	if is_backend_down():
		return render_template('error.html')

	if request.method == 'GET':
		if not is_wallet_locked():
			return redirect(url_for('joinmarketgui_endpoint.balance'))
		
		# get list of wallets from Joinmarket
		r = req.get(API_URL + '/wallet/all', verify=CERT)
		listWallets = r.json()['wallets']
		if listWallets == []:
			return redirect(url_for('joinmarketgui_endpoint.create'))
		# prepare template data dictionary
		templateData = {
			'wallet_unlocked': False,
			'wallets': listWallets
		}
		# render unlock page with list of wallets in <select>
		return render_template('unlock.html', **templateData)
	else:
		# POST request to unlock wallet
		walletName = request.form['walletname']
		passwordJSON = {'password': request.form['password']}
		r = req.post(API_URL + '/wallet/' + walletName + '/unlock', json=passwordJSON, verify=CERT)
		if r.status_code == 200:
			# save the TOKEN
			set_token(r.json()['token'])
			# confirm the session is unlocked
			r = req.get(API_URL + '/session', verify=CERT).json()
			assert(walletName == r['wallet_name'])
			# flash success alert
			flash("Wallet unlocked successfully!", category="success")
			# redirect to balance page
			return redirect(url_for('joinmarketgui_endpoint.balance'))
		else:
			flash("Error unlocking! Check password.", category="danger")
			return redirect(url_for('joinmarketgui_endpoint.unlock'))

@joinmarketgui_endpoint.route("/create", methods=['GET', 'POST'])
@app.csrf.exempt
def create():
	if is_backend_down():
		return render_template('error.html')

	if request.method == 'GET':
		if is_wallet_locked():
			return render_template('create.html')
		return redirect(url_for('joinmarketgui_endpoint.index'))

	else: # handle POST request
		walletJSON = {
			'walletname': request.form['walletname'],
			'password': request.form['password'],
			'wallettype': request.form['wallettype']
		}
		r = req.post(API_URL + '/wallet/create', json=walletJSON, verify=CERT)
		if r.status_code == 200:
			token = r.json()['token']
			set_token(token)
			flash("Wallet created successfully!", category="success")
			return redirect(url_for('joinmarketgui_endpoint.balance'))

@joinmarketgui_endpoint.route("/balance")
@app.csrf.exempt
def balance():
	if is_backend_down():
		return render_template('error.html')

	if is_wallet_locked():
		return redirect(url_for('joinmarketgui_endpoint.unlock'))

	if not is_token_present():
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)

	r = req.get(API_URL + '/session', verify=CERT).json()
	walletName = r['wallet_name']
	makerRunning = r['maker_running']
	coinjoinRunning = r['coinjoin_in_process']

	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(API_URL + '/wallet/'+walletName+'/display', headers=authHeader, verify=CERT)

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
		print(r)
		return r.json()

@joinmarketgui_endpoint.route("/lock")
def lock():
	if is_backend_down():
		return render_template('error.html')

	if is_wallet_locked():
		return redirect(url_for('joinmarketgui_endpoint.unlock'))

	r = req.get(API_URL + '/session', verify=CERT).json()
	walletName = r['wallet_name']
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(API_URL + '/wallet/'+walletName+'/lock', headers=authHeader, verify=CERT)
	if r.status_code == 200:
		delete_token()
		flash('Wallet locked!', category="success")
		return redirect(url_for('unlock'))
	else:
		return redirect(url_for('balance'))

@joinmarketgui_endpoint.route("/deposit")
def deposit(address=None):
	if is_backend_down():
		return render_template('error.html')

	if is_wallet_locked():
		return redirect(url_for('joinmarketgui_endpoint.unlock'))

	if not is_token_present():
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)

	if address == None:
		r = req.get(API_URL + '/session', verify=CERT).json()
		walletName = r['wallet_name']
		authHeader = {'Authorization': 'Bearer ' + get_token()}
		r = req.get(API_URL + '/wallet/'+walletName+'/address/new/0', headers=authHeader, verify=CERT)

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

@joinmarketgui_endpoint.route("/withdraw", methods=['GET', 'POST'])
def withdraw():
	if is_backend_down():
		return render_template('error.html')

	if not is_token_present():
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)

	if request.method == 'GET':
		if is_wallet_locked():
			return redirect(url_for('joinmarketgui_endpoint.unlock'))

		templateData = {
			'wallet_unlocked': True
		}
		return render_template('withdraw.html', **templateData)
	else:
		r = req.get(API_URL + '/session', verify=CERT).json()
		walletName = r['wallet_name']

		authHeader = {'Authorization': 'Bearer ' + get_token()}
		url = API_URL + '/wallet/'+walletName+'/taker/direct-send'
		r = req.post(url, headers=authHeader, json=request.form, verify=CERT)
		if r.status_code == 200:
			flash("Funds withdrawn successfully!", category="success")
			return redirect(url_for("balance"))
		else:
			flash("Error withdrawing funds. Error code: " + str(r.status_code), category="danger")
			return render_template("withdraw.html")

@joinmarketgui_endpoint.route("/yg")
def yg():
	if is_backend_down():
		return render_template('error.html')

	if is_wallet_locked():
		return redirect(url_for('joinmarketgui_endpoint.unlock'))

	if not is_token_present():
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)

	r = req.get(API_URL + '/session', verify=CERT).json()
	walletName = r['wallet_name']
	makerRunning = r['maker_running']

	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(API_URL + '/wallet/'+walletName+'/display', headers=authHeader, verify=CERT)
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

@joinmarketgui_endpoint.route("/getfbaddress", methods=['POST'])
def getfbaddress():
	r = req.get(API_URL + '/session', verify=CERT).json()
	walletName = r['wallet_name']
	lockDate = request.form['lockdate-year'] + '-' + request.form['lockdate-month']
	url = API_URL + '/wallet/' + walletName + '/address/timelock/new/' + lockDate
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(url, headers=authHeader, verify=CERT)
	if r.status_code == 200:
		address = r.json()['address']
		return deposit(address)
	else:
		templateData = {
			"error": "Can't create Fidelity bond. Error code:" + str(r.status_code)
		}
		return render_template('error.html', **templateData)

@joinmarketgui_endpoint.route("/start-yg", methods=['POST'])
@app.csrf.exempt
def startYG():
	r = req.get(API_URL + '/session', verify=CERT).json()
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
	r = req.post(url, headers=authHeader, json=ygConfig, verify=CERT)
	flash('Maker started successfully!', category="success")
	return redirect(url_for('balance'))

@joinmarketgui_endpoint.route("/stop-yg")
@app.csrf.exempt
def stopYG():
	r = req.get(API_URL + '/session', verify=CERT).json()
	walletName = r['wallet_name']
	url = API_URL + '/wallet/' + walletName + '/maker/stop'
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(url, headers=authHeader, verify=CERT)
	flash('Maker stopped successfully!', category="success")
	return redirect(url_for('balance'))

@joinmarketgui_endpoint.route("/coinjoin", methods=['GET', 'POST'])
def coinjoin():
	if is_backend_down():
		return render_template('error.html')

	if not is_token_present():
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)

	if request.method == 'GET':
		if is_wallet_locked():
			return redirect(url_for('unlock'))
		
		templateData = {
			'wallet_unlocked': True,	
		}
		return render_template('coinjoin.html', **templateData)
	else:
		r = req.get(API_URL + '/session', verify=CERT).json()
		walletName = r['wallet_name']

		authHeader = {'Authorization': 'Bearer ' + get_token()}
		url = API_URL + '/wallet/'+walletName+'/taker/coinjoin'
		r = req.post(url, headers=authHeader, json=request.form, verify=CERT)
		if r.status_code == 200:
			flash("Coinjoin submitted successfully!", category="success")
			return redirect(url_for("balance"))
		else:
			return r.json()

@joinmarketgui_endpoint.route("/about")
def about():
	return render_template("about.html")

@joinmarketgui_endpoint.route("/get_qr_code")
def get_qr_code():
	url = request.args.get('url')
	img_buf = BytesIO()
	img = generate_qr_code(url)
	img.save(img_buf)
	img_buf.seek(0)
	return send_file(img_buf, mimetype='image/png')

@joinmarketgui_endpoint.route("/settings", methods=['GET', 'POST'])
def settings():
	if is_backend_down():
		return render_template('error.html')

	if is_wallet_locked():
		return redirect(url_for('unlock'))

	if not is_token_present():
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)

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
	templateData = {
		'settings': settingsData,
		'wallet_unlocked': True
	}
	return render_template('settings.html', **templateData)

@joinmarketgui_endpoint.route("/showseed")
def showseed():
	if is_backend_down():
		return render_template('error.html')

	if is_wallet_locked():
		return redirect(url_for('unlock'))

	if not is_token_present():
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)

	r = req.get(API_URL + '/session', verify=CERT).json()
	walletName = r['wallet_name']
	url = API_URL + '/wallet/' + walletName + '/getseed'
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(url, headers=authHeader, verify=CERT)
	seedphrase = r.json()['seedphrase'].split()
	templateData = {
		'seedphrase': seedphrase,
		'wallet_unlocked': True
	}
	return render_template('seed.html', **templateData)

@joinmarketgui_endpoint.route("/utxos")
def utxos():
	if is_backend_down():
		return render_template('error.html')

	if is_wallet_locked():
		return redirect(url_for('unlock'))

	if not is_token_present():
		templateData = {
			'error': 'Session token missing. Joinmarket GUI is already open from another browser.'
		}
		return render_template('error.html', **templateData)

	r = req.get(API_URL + '/session', verify=CERT).json()
	walletName = r['wallet_name']
	url = API_URL + '/wallet/' + walletName + '/utxos'
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(url, headers=authHeader, verify=CERT)
	templateData = {
		'utxos': r.json()['utxos'],
		'wallet_unlocked': True
	}
	# return r.json()['utxos']
	return render_template('utxos.html', **templateData)

@joinmarketgui_endpoint.errorhandler(404)
def not_found(e):
	return render_template('404.html')

