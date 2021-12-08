from flask import Flask, render_template, redirect, url_for, request
import requests as req
import os
import logging

app = Flask(__name__)

API_IP = "10.0.0.4"
API_PORT = 28183
API_URL = "https://" + API_IP + ":" + str(API_PORT) + "/api/v1"

MINSIZE = 100000

def get_token():
	f = open("token.dat", "r")
	token = f.read()
	f.close()
	return token

def set_token(token):
	f = open("token.dat", "w")
	f.write(token)
	f.close()

def delete_token():
	os.remove('token.dat')

def save_seedphrase(seedphrase):
	f = open('seed.dat', 'w')
	f.write(seedphrase)
	f.close()

def get_seedphrase():
	f = open('seed.dat', 'r')
	seedphrase = f.read()
	f.close()
	return seedphrase

def delete_seedphrase():
	os.remove('seed.dat')

def comma_seperated_sats(balance):
	balance_str = str(balance)
	ans = ''
	for i in range(0,len(balance_str)):
		ans += balance_str[len(balance_str)-i-1]
		if i%3==2 and i<len(balance_str)-1:
			ans += ','
	return ans[::-1]

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
			# redirect to balance page
			return redirect(url_for('balance'))
		else:
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
			seedphrase = r.json()['seedphrase']
			token = r.json()['token']
			set_token(token)
			save_seedphrase(seedphrase)
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
		return render_template('withdraw.html')
	else:
		r = req.get(API_URL + '/session', verify=False).json()
		walletName = r['wallet_name']

		authHeader = {'Authorization': 'Bearer ' + get_token()}
		url = API_URL + '/wallet/'+walletName+'/taker/direct-send'
		r = req.post(url, headers=authHeader, json=request.form, verify=False)
		if r.status_code == 200:
			return redirect(url_for("balance"))
		else:
			return r.json()


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
	return redirect(url_for('balance'))

@app.route("/stop-yg")
def stopYG():
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	url = API_URL + '/wallet/' + walletName + '/maker/stop'
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(url, headers=authHeader, verify=False)
	return redirect(url_for('balance'))

@app.route("/coinjoin", methods=['GET', 'POST'])
def coinjoin():
	if request.method == 'GET':
		return render_template('coinjoin.html')
	else:
		r = req.get(API_URL + '/session', verify=False).json()
		walletName = r['wallet_name']

		authHeader = {'Authorization': 'Bearer ' + get_token()}
		url = API_URL + '/wallet/'+walletName+'/taker/coinjoin'
		r = req.post(url, headers=authHeader, json=request.form, verify=False)
		app.logger.info("Coinjoin POST status code: %s", r.status_code)
		if r.status_code == 200:
			return redirect(url_for("balance"))
		else:
			return r.json()

@app.route("/about")
def about():
	return render_template("about.html")