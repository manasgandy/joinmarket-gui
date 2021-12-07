from flask import Flask, render_template, redirect, url_for, request
import requests as req

app = Flask(__name__)

API_URL = "https://10.0.0.18:28183/api/v1"
TOKEN = ""

@app.route("/")
def index_page():
	r = req.get(API_URL + '/session', verify=False).json()
	if r['wallet_name'] == "None":
		return redirect(url_for('unlock'))
	else:
		return redirect(url_for('balance'))


@app.route("/unlock", methods=['GET', 'POST'])
def unlock():
	global TOKEN
	if request.method == 'GET':
		# get list of wallets from Joinmarket
		r = req.get(API_URL + '/wallet/all', verify=False)
		# prepare tempalte data dictionary
		templateData = {
			'wallets': r.json()['wallets']
		}
		# render unlock page with list of wallets in <select>
		return render_template('unlock.html', **templateData)
	else:
		# POST request to unlock wallet
		walletName = request.form['walletname']
		passwordJSON = {'password': request.form['password']}
		r = req.post(API_URL + '/wallet/' + walletName + '/unlock', json=passwordJSON, verify=False)
		if r.status_code == 200:
			# save the TOKEN
			TOKEN = r.json()['token']
			# confirm the session is unlocked
			r = req.get(API_URL + '/session', verify=False).json()
			assert(walletName == r['wallet_name'])
			# redirect to balance page
			return redirect(url_for('balance'))
		else:
			return redirect(url_for('unlock'))


@app.route("/balance")
def balance():
	global TOKEN
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	authHeader = {'Authorization': 'Bearer ' + TOKEN}
	r = req.get(API_URL + '/wallet/'+walletName+'/display', headers=authHeader, verify=False)
	if r.status_code == 200:
		walletInfo = r.json()['walletinfo']
		templateData = {
			'balance_sats': round(float(walletInfo['total_balance'])*1e8)
		}
		return render_template('balance.html', **templateData)
	else:
		return r.json()

@app.route("/lock")
def lock():
	global TOKEN
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	authHeader = {'Authorization': 'Bearer ' + TOKEN}
	r = req.get(API_URL + '/wallet/'+walletName+'/lock', headers=authHeader, verify=False)
	if r.status_code == 200:
		return redirect(url_for('unlock'))
	else:
		return redirect(url_for('balance'))

@app.route("/deposit")
def deposit():
	global TOKEN

	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	authHeader = {'Authorization': 'Bearer ' + TOKEN}
	r = req.get(API_URL + '/wallet/'+walletName+'/address/new/0', headers=authHeader, verify=False)

	if r.status_code == 200:
		templateData = {
			'address': r.json()['address']
		}
		return render_template('deposit.html', **templateData)
	else:
		return r.json()

@app.route("/yg")
def yg():
	return render_template('yg.html')

@app.route("/getfbaddress", methods=['POST'])
def getfbaddress():
	global TOKEN

	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	lockDate = request.form['lockdate-year'] + '-' + request.form['lockdate-month']
	authHeader = {'Authorization': 'Bearer ' + TOKEN}
	r = req.get(API_URL + '/wallet/'+walletName+'/address/timelock/new/'+lockDate, headers=authHeader, verify=False)

	return r.json()