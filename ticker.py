#!/usr/bin/python
# Ticker.py
#
# This background script periodically gets the btc/dvc ticker price from crypto-trade.com and vircurex, the usd/btc from bitstamp, btc-e, mtgox and bitfinex, 
# and combines them to get an average usd/dvc price
#
# It collates this information once per minute, and stores the price in a database, which is read by the webserver
#

import urllib2, json, time, web, psycopg2, sys, datetime

class Ticker(object):
	
	def __init__(self):
		db = json.load(open("db.access"))
		self.db = web.database(dbn=str(db['type']), db=str(db['name']), user=str(db['user']), pw=str(db['pass']))
		self.last_ticker_id = self.db.query("select id from ticker order by time desc limit 1")[0].id
		self.last_candle_id = self.db.query("select id from candle15 order by time desc limit 1")[0].id
		#print self.last_ticker_id
		#print self.last_candle_id
		self.max_frame_time = 60
		self.usddvc = 0.0

	def GetRequest(self, path):
		try:
			response = urllib2.urlopen(path)
			return json.load(response)
		except:
			raise

	def GetGox(self):
		path = 'https://data.mtgox.com/api/2/BTCUSD/money/ticker_fast'
		try:
			result = self.GetRequest(path)
			if result['result'] == 'success':
				return float(result['data']['last']['value'])
			else:
				return None
		except:
			return None
	
	def GetBitstamp(self):
		path = 'https://www.bitstamp.net/api/ticker'
		try:
			result = self.GetRequest(path)
			if result['last'] != None:
				return float(result['last'])
			else:
				return None
		except:
			return None
			
	def GetBTCe(self):
		path = 'https://btc-e.com/api/2/btc_usd/ticker'
		try:
			result = self.GetRequest(path)
			if result['ticker'] != None:
				return float(result['ticker']['last'])
			else:
				return None
		except:
			return None

	def GetBitfinex(self):
		path = 'https://api.bitfinex.com/v1/ticker/btcusd'
		try:
			req = urllib2.Request(path, headers={'User-Agent':"Magic Browser"})
			con = urllib2.urlopen(req)
			result = json.load(con)
			if result['last_price'] != None:
				return float(result['last_price'])
			else:
				return None
		except:
			return None
	
	def GetCryptoTrade(self):
		path = 'https://crypto-trade.com/api/1/ticker/dvc_btc'
		try:
			result = self.GetRequest(path)
			if result['status'] == 'success':
				return float(result['data']['last'])
			else:
				return None
		except:
			return None

	def GetVircurex(self):
		path = 'https://vircurex.com/api/get_last_trade.json?base=DVC&alt=BTC'
		try:
			req = urllib2.Request(path, headers={'User-Agent':"Magic Browser"})
			con = urllib2.urlopen(req)
			result = json.load(con)
			if result['value'] != None:
				return float(result['value'])
			else:
				return None
		except:
			return None
		
	def CalcAverage(self, prices):
		average = 0
		if len(prices) > 0:
			count = 0
			#print "There are %d prices to average" % len(prices)
			for price in prices:
				average += price
				count += 1
			average = average / count
		return average


	def GetUSDBTC(self):
		# go through all the usd/btc exchanges to get an average price of bitcoins
		try:
			prices = []
			# go through all the exchanges and get their prices here
			result = self.GetGox()
			if result != None:
				prices.append(result)
			result = self.GetBitstamp()
			if result != None:
				prices.append(result)
			result = self.GetBTCe()
			if result != None:
				prices.append(result)
			result = self.GetBitfinex()
			if result != None:
				prices.append(result)			
			# figure out the average USD/BTC
			return self.CalcAverage(prices)
		except:
			raise

	def GetBTCDVC(self):
		# go through all the btc/dvc exchanges to get an average price of devcoins
		try:
			prices = []
			# go through all the exchanges and get their prices here
			result = self.GetCryptoTrade()
			if result != None:
				prices.append(result)
			result = self.GetVircurex()
			if result != None:
				prices.append(result)

			# figure out the average BTC/DVC
			return self.CalcAverage(prices)	
		except:
			raise


	def Run(self):
		# Once a minute, get the average prices of bitcoins and devcoins, work out the price of dvc in USD,
		# Update the ticker and candle tables with data as it arrives
		while True:
			frame_start_time = time.time()
			# calculate average price of USD/dvc
			try:
				self.usddvc = self.GetUSDBTC() * self.GetBTCDVC()
				#print self.usddvc
				timestr = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
				self.db.query("insert into ticker (time, price) values (TIMESTAMP $time, $price)", vars={'time':timestr, 'price':self.usddvc})
				self.last_ticker_id += 1		
			except:
				raise
			# now update the candlestick
			try:
				if self.last_ticker_id % 15 == 1:	# We've reached a 15-min milestone
					#print "Creating NEW candle: (%f, %f, %f, %f)" % (self.usddvc, self.usddvc, self.usddvc, self.usddvc)
					self.db.query("insert into candle15 (time, open, close, high, low) values (TIMESTAMP $time, $ticker, $ticker, $ticker, $ticker)", vars={'time':timestr, 'ticker':self.usddvc})
					self.last_candle_id += 1
				else:
					last_values = self.db.query("select close, low, high from candle15 where id = $candleid", vars={'candleid':self.last_candle_id})[0]
					last_values['close'] = self.usddvc
					if self.usddvc > last_values['high']:	# current price is higher than current high
						last_values['high'] = self.usddvc
					elif self.usddvc < last_values['low']:	# current price is less than current low
						last_values['low'] = self.usddvc
					# update db with new candle values
					#print "Updating candle: (%f, %f, %f)" % (last_values['close'], last_values['low'], last_values['high'])
					self.db.query("update candle15 set close=$close, low = $low, high = $high where id = $candleid", vars={'close':last_values['close'], 'low':last_values['low'], 'high':last_values['high'],'candleid':self.last_candle_id})
			except Exception as e:
				str = datetime.datetime.now().strftime("%y-%m-%d %H:%M") + ' ' + str(e)
				file = open("tickererror.log", "a")
				file.write(str+"\n")

			# Apply throttle
			frame_time = time.time() - frame_start_time
			if frame_time < self.max_frame_time:
				timeleft = self.max_frame_time - frame_time
				print "sleeping for %.8f seconds" % timeleft
				time.sleep(timeleft)

Ticker().Run()
