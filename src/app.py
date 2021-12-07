from flask import Flask, render_template, redirect, url_for, request
import requests as req
import os
import logging

app = Flask(__name__)

API_IP = "10.0.0.18"
API_PORT = 28183
API_URL = "https://" + API_IP + ":" + str(API_PORT) + "/api/v1"

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
		authHeader = {'Authorization': 'Bearer ' + get_token()}
		r = req.get(API_URL + '/wallet/'+walletName+'/display', headers=authHeader, verify=False)
		if r.status_code == 200:
			walletInfo = r.json()['walletinfo']
			templateData = {
				'balance_sats': round(float(walletInfo['total_balance'])*1e8)
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

@app.route("/yg")
def yg():
	return render_template('yg.html')

@app.route("/getfbaddress", methods=['POST'])
def getfbaddress():
	r = req.get(API_URL + '/session', verify=False).json()
	walletName = r['wallet_name']
	lockDate = request.form['lockdate-year'] + '-' + request.form['lockdate-month']
	url = API_URL + '/wallet/' + walletName + '/address/timelock/new/' + lockDate
	authHeader = {'Authorization': 'Bearer ' + get_token()}
	r = req.get(url, headers=authHeader, verify=False)
	address = r.json()['address']
	return deposit(address)