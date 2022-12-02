from replit import db
from flask import Flask, render_template, request, flash
from flask_xcaptcha import XCaptcha
from os import environ
import requests
import re
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import threading
import math
import bananopie
from pycoingecko import CoinGeckoAPI
from time import sleep, time
from waitress import serve

app = Flask(__name__, static_folder='static', static_url_path='')

# Config
app.config['SECRET_KEY'] = environ.get("FLASK_SECRET")

app.config['XCAPTCHA_SITE_KEY'] = "4c2f8a95-909a-484f-bf84-08576d905869"
app.config['XCAPTCHA_SECRET_KEY'] = environ.get("HCAPTCHA_SECRET")
app.config['XCAPTCHA_VERIFY_URL'] = "https://hcaptcha.com/siteverify"
app.config['XCAPTCHA_API_URL'] = "https://hcaptcha.com/1/api.js"
app.config['XCAPTCHA_DIV_CLASS'] = "h-captcha"
app.config['XCAPTCHA_THEME'] = 'dark'

xcaptcha = XCaptcha(app=app)

cg = CoinGeckoAPI()

limiter = Limiter(app,
                  key_func=get_remote_address,
                  default_limits=["100 per minute"])

rpc = bananopie.RPC("https://kaliumapi.appditto.com/api")
account = bananopie.Wallet(rpc, seed=environ["SEED"], index=0)


def update():
    while True:
        # Update balance, price, and recieve pending deposits
        db["balance"] = int(account.get_balance()["balance"])
        db["price"] = cg.get_price(ids='banano',
                                   vs_currencies='usd')["banano"]["usd"]
        try:
            account.receive_all()
        except:
            pass
        sleep(120)


def getIP():
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return request.environ['REMOTE_ADDR']
    elif request.environ['HTTP_X_FORWARDED_FOR'] is None:
        return False
    else:
        return request.environ['HTTP_X_FORWARDED_FOR']


def clean():
    while True:
        for key in db.keys():
            if key not in ["balance", "price", "sent", "claims"
                           ] and time() - db[key] > 86400:
                del db[key]
        sleep(86400)


tUpdate = threading.Thread(target=update)
tClean = threading.Thread(target=clean)
tUpdate.start()
tClean.start()


@app.route('/', methods=('GET', 'POST'))
def index():
    if request.method == 'POST':
        claim = True
        # Check if captcha is valid
        if not xcaptcha.verify():
            claim = False
            flash("Invalid Captcha")

        # Check if the faucet still has funds
        if claim and db["balance"] < 5e29:
            claim = False
            flash("Sorry, the faucet is dry")

        # Check if user has claimed already
        if claim and ((request.form["address"] in db.keys()
                       and time() - db[request.form["address"]] < 86400) or
                      (getIP() in db.keys() and time() - db[getIP()] < 86400)):
            claim = False
            try:
                m, s = divmod(
                    86400 - int(time() - db[request.form["address"]]), 60)
            except:
                m, s = divmod(86400 - int(time() - db[getIP()]), 60)
            h, m = divmod(m, 60)
            h = str(h) + ' hours ' if h > 1 else str(
                h) + ' hour ' if h == 1 else ''
            m = str(m) + ' minutes ' if m > 1 else str(
                m) + ' minute ' if m == 1 else ''
            s = str(s) + ' seconds' if s > 1 else str(
                s) + ' second' if s == 1 else ''
            flash(
                'Your address or IP has already claimed from the faucet, try again in '
                + h + m + s)

        # Check if address is valid
        if claim:
            address = request.form["address"]
            validPattern = re.compile(
                "/^ban_[13]{1}[13456789abcdefghijkmnopqrstuwxyz]{59}$/")
            if not validPattern.match(address):
                claim = False
                flash("Invalid Address")
            else:
                try:
                    history = rpc.get_account_history(address)["history"]
                except:
                    flash(
                        "Sorry, there seems to be a problem with the server. Please try again later."
                    )
                if len(history) == 0:
                    claim = False
                    flash(
                        "Sorry, unopened accounts cannot claim from the faucet"
                    )

        # Check if IP is good
        if claim:
            ipResult = requests.get('http://proxycheck.io/v2/' + getIP() +
                                    '?key=' +
                                    environ.get("PROXYCHECK_API_KEY") +
                                    '&vpn=1&risk=1').json()
            if ipResult["status"] != "denied" and (
                    ipResult["status"] == "error"
                    or ipResult[getIP()]["risk"] >= 67 or
                (ipResult[getIP()]["proxy"] == "yes"
                 and ipResult[getIP()]["type"] != "VPN")):
                claim = False
                flash("VPN, Proxy, or Bad IP detected")

        if claim:
            # Set reward
            triple = False
            reward = 0.000167 / db["price"] if db[
                "balance"] >= 1e31 else 0.000167 / db["price"] * (
                    0.5 - math.cos(math.pi * (db["balance"] / 1e31)) / 2)
            if request.form["ab"] == "False":
                reward *= 3
                triple = True
            # Send reward
            try:
                account.send(address, float(str(reward)[:6]))
                # Reset countdown
                current = time()
                db[request.form["address"]] = current
                db[getIP()] = current
                db["claims"] += 1
                db["sent"] += float(str(reward)[:6])
                flash("Success! Sent " + float(str(reward)[:6]) + " $BAN to " +
                      address)
                if triple:
                    flash("Your reward has been tripled")
            except:
                flash(
                    "Sorry, there seems to be a problem with the server. Please try again later."
                )

    messages = {
        'balance':
        str(db["balance"] / 1e29)[:6],
        'reward':
        str(0.000167 / db["price"] if db["balance"] >= 1e31 else 0.000167 /
            db["price"] * (0.5 - math.cos(math.pi *
                                          (db["balance"] / 1e31)) / 2))[:6]
    }
    return render_template('index.html', messages=messages)


serve(app, host='0.0.0.0', port=8080, url_scheme='https')
