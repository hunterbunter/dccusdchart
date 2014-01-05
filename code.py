#!/usr/bin/env python
import web
import urllib, re
import time, calendar
import json
from modules import receiver

# Uncomment this and make it false if you want to turn off browser debugging (important for release!)
#web.config.debug = False


urls = (
	'/', 'index',
	'/shares', 'shares',
)

app = web.application(urls, locals())
db = json.load(open("db.access"))
db = web.database(dbn=str(db['type']), db=str(db['name']), user=str(db['user']), pw=str(db['pass']))

if web.config.get('_session') is None:
	store = web.session.DBStore(db, 'sessions')
	session = web.session.Session(app, store, initializer={'name':0, 'round':0})
	web.config._session = session
else:
	session = web.config._session

# set session parameters
web.config.session_parameters.update(cookie_name="tasty_cookie", cookie_domain="blisteringdevelopers.com")

render = web.template.render('templates', base='base', globals={})

def create_render():
	return web.template.render('templates', base='base' )
		
class index:
	def GET(self):
		response = urllib.urlopen('http://faucet.d.evco.in').read()
		response = iter(response.split(' '))
		for row in response:
			if 'Blockcount' in row:
				block = re.sub('[^0-9]+', '', response.next())	
		blocksleft = 4000 - int(block)%4000

		round = (int(block) + blocksleft)/4000

		minleft = blocksleft * 10
		h, m = divmod(minleft, 60)
		d, h = divmod(h, 24)
		timeleft = "%d days, %d hours and %d minutes" % (d, h, m)

		secondstogo = blocksleft * 600
		eta = calendar.timegm(time.gmtime()) + secondstogo
		eta = time.strftime("%a, %d %b %Y %H:%M +0000", time.gmtime(eta))

		if blocksleft > 2700: # the current payout block is still active
			activeround = round
			activeroundstart = ((round - 1) * 4000) - 2700
		else:
			activeround = round + 1
			activeroundstart = (round * 4000) - 2700
		activeroundend = activeroundstart + 4000

		activeshares, breakdown, name, myshares, tally = receiver.GetShareEstimate(activeround, session.name, session.round)
		activepayout = 180000000/activeshares
		
		activeblocksleft = activeroundend - int(block)
		activeminleft = activeblocksleft * 10
		h, m = divmod(activeminleft, 60)
		d, h = divmod(h, 24)
		activetimeleft = "%d days, %d hours and %d minutes" % (d, h, m)

		activesecondstogo = activeblocksleft * 600
		activeendtime = calendar.timegm(time.gmtime()) + activesecondstogo
		activeendtime = time.strftime("%a, %d %b %Y %H:%M +0000", time.gmtime(activeendtime))

		devpershare = receiver.GetSharesByRound(round)

		prev = {}
		prev['round'] = round - 1
		prev['devpershare'] = receiver.GetSharesByRound(round - 1)

		return render.index(name, myshares, tally, session.round, block, round, blocksleft, timeleft, eta, activeround, activeshares, activepayout, activeroundstart, activeroundend, activeendtime, activetimeleft, devpershare, breakdown, prev) 

class shares:
	def POST(self):
		name, round = web.input().name, web.input().round
		session['name'] = name
		session['round'] = round
		raise web.seeother("/")

if __name__ == "__main__":
	web.wsgi.runwsgi = lambda func, addr=None: web.wsgi.runfcgi(func, addr)
	app.run()
