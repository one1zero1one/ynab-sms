from twilio.rest import Client
from slackclient import SlackClient
from structlog import get_logger
import schedule
import time
import requests
import json

# Init logger
log = get_logger()

# Load config data once, on startup
try:
	with open('settings.json', 'r') as f:
		settings = json.load(f)
		log.msg("Loading config on startup", file=f)
except:
	log.err("Error loading settings. Verify that settings.json exists and contains valid json!")
	exit(-1)

# Fill flags from config
flags = {}
for user in settings['users']:
	flags[user['flag']] = user['name']

# Init Slack from config - TODO when slack is in notification list, check if token and channel defined.
sc = SlackClient(settings['slack']['token'])

def sendSMS(number, message):
	twilio = Client(settings['twilio']['sid'], settings['twilio']['token'])
	twilio.messages.create(to=number, from_=settings['twilio']['number'], body=message)
	log.msg("SMS message", to=number, from_=settings['twilio']['number'], body=message)

def sendSlack(message):
	sc.api_call("chat.postMessage", username='ynab-sms', icon_emoji=':money_with_wings:', channel=settings['slack']['channel'], text=message)
	log.msg("Slack message", channel=settings['slack']['channel'], text=message)

def processTransaction(id, doc, balance, knownTransactions, init):
	if id not in knownTransactions:
		knownTransactions.append(id)
		# send sms message to the _other_ users
		if doc['flag'] in flags and doc['outflow'] > 0 and ( init == 0 ):
			#SMS
			if 'twilio' in settings['notify']:			
				for user in settings['users']:
					if user['flag'] not in doc['flag']:
						text = flags[doc['flag']] + ' spent ' + settings['coin'] + '{:01.2f}'.format(doc['outflow']) + ' @ ' + doc['payee'] + ' from ' + doc['category'] + ' in account ' + doc['account'] + '. '  + settings['coin'] + '{:01.2f}'.format(balance) + ' remaining. (' + doc['memo'] + ')'
						sendSMS(user['number'], text)
		# send message to slack channel
		if doc['outflow'] > 0 and ( init == 0 ) and 'slack' in settings['notify']:
			if doc['flag'] in flags:
				who = flags[doc['flag']]
			else:
				who = "Someone"
			text = who + ' spent ' + settings['coin'] + '{:01.2f}'.format(doc['outflow']) + ' @ ' + doc['payee'] + ' from ' + doc['category'] + ' in account ' + doc['account'] + '. ' + settings['coin'] + '{:01.2f}'.format(balance) + ' remaining. (' + doc['memo'] + ')'
			sendSlack(text)

def job():
	log.msg("Starting job")
	
	init = 0
	docs = []

	# Load previous transactions
	try:
		with open('known-transactions.json', 'r') as f:
			knownTransactions = json.load(f)
			log.msg("Loading known transactions", file=f)
	except:
		knownTransactions = []
		init = 1
		log.msg("No known transactions")

	# Load previous budget amounts
	try:
		with open('budgeted-amounts.json', 'r') as f:
			budgetedAmounts = json.load(f)
			log.msg("Loading previous bugeted amounts", file=f)
	except:
		budgetedAmounts = {}
		init = 1
		log.msg("No previous bugeted amounts")

	# Grab the current data from the YNAB API
	headers = {
		'accept': 'application/json',
		'Authorization': 'Bearer ' + settings['ynab']['token']
	}

	ynabURL = 'https://api.youneedabudget.com/v1'
	budgetURL = ynabURL + '/budgets/' + settings['ynab']['budget']

	data = None

	r = requests.get(budgetURL + '/transactions', headers=headers)
	r.raise_for_status()
	log.msg("Got /transactions", duration=r.elapsed.microseconds, size=len(r.content))

	data = r.json()	
	transactions = data['data']['transactions']

	# Get the Category list
	r = requests.get(budgetURL + '/categories', headers=headers)
	r.raise_for_status()
	log.msg("Got /categories", duration=r.elapsed.microseconds, size=len(r.content))
	
	data = r.json()
	
	categories = {}
	for g in data['data']['category_groups']:
		for c in g['categories']:
			if c['id'] in budgetedAmounts:
				if c['budgeted'] != budgetedAmounts[c['id']]:				
					if c['budgeted'] > budgetedAmounts[c['id']]: 
						amount = (c['budgeted'] - budgetedAmounts[c['id']]) / 1000.0
						text = 'The amount budgeted for ' + c['name'] + ' has increased by ' + settings['coin'] + '{:01.2f}'.format(amount) + '. There is now ' + settings['coin'] + '{:01.2f}'.format(c['balance'] / 1000.0) + ' remaining.'
					else:
						amount = (budgetedAmounts[c['id']] - c['budgeted']) / 1000.0
						text = 'The amount budgeted for ' + c['name'] + ' has decreased by '+ settings['coin'] + '{:01.2f}'.format(amount) + '. There is now ' + settings['coin'] + '{:01.2f}'.format(c['balance'] / 1000.0) + ' remaining.'
					#SMS
					if 'twilio' in settings['notify']:			
						for user in settings['users']:
							sendSMS(user['number'], text)
					if 'slack' in settings['notify']:
						sendSlack(text)

			budgetedAmounts[c['id']] = c['budgeted']
			
			categories[c['id']] = {}
			categories[c['id']]['name'] = c['name']
			categories[c['id']]['balance'] = c['balance'] / 1000.0
			categories[c['id']]['budgeted'] = c['budgeted'] / 1000.0
			categories[c['id']]['group'] = g['name']

	# Get the Payee list
	r = requests.get(budgetURL + '/payees', headers=headers)
	r.raise_for_status()
	log.msg("Got /payees", duration=r.elapsed.microseconds, size=len(r.content))
	
	data = r.json()

	payees = {}
	for p in data['data']['payees']:
		payees[p['id']] = p['name']

	# Process Transactions
	for t in transactions:
		# Check to see if this is a split transaction
		if len(t['subtransactions']) > 0:
			for s in t['subtransactions']:
				id = s['id']			
				doc = {}
				doc['date'] = t['date']
				doc['amount'] = s['amount'] / 1000.0
				if doc['amount'] < 0:
					doc['outflow'] = doc['amount'] * -1
					doc['inflow'] = 0
				else:
					doc['outflow'] = 0
					doc['inflow'] = doc['amount']
				if s['memo'] is not None:
					doc['memo'] = s['memo']
				elif t['memo'] is not None:
					doc['memo'] = t['memo']
				else:
					doc['memo'] = ''
				doc['status'] = t['cleared']
				doc['approved'] = t['approved']
				doc['flag'] = t['flag_color']
				doc['account'] = t['account_name']
				if s['payee_id'] is not None:
					doc['payee'] = payees[s['payee_id']]
				elif t['payee_id'] is not None:
					doc['payee'] = payees[t['payee_id']]
				doc['category'] = None
				doc['group'] = None
				catBalance = None
				if s['category_id'] is not None:
					doc['category'] = categories[s['category_id']]['name']
					doc['group'] = categories[s['category_id']]['group']
					catBalance = categories[s['category_id']]['balance']
				elif t['category_id'] is not None:
					doc['category'] = categories[t['category_id']]['name']
					doc['group'] = categories[t['category_id']]['group']
					catBalance = categories[t['category_id']]['balance']            
				processTransaction(id, doc, catBalance, knownTransactions, init)
		else:
			id = t['id']
			doc = {}
			doc['date'] = t['date']
			doc['amount'] = t['amount'] / 1000.0
			if doc['amount'] < 0:
				doc['outflow'] = doc['amount'] * -1
				doc['inflow'] = 0
			else:
				doc['outflow'] = 0
				doc['inflow'] = doc['amount']
			if t['memo'] is not None:
				doc['memo'] = t['memo']
			else:
				doc['memo'] = ''
			doc['status'] = t['cleared']
			doc['approved'] = t['approved']
			doc['flag'] = t['flag_color']
			doc['account'] = t['account_name']
			if t['payee_id'] is not None:
				doc['payee'] = payees[t['payee_id']]
			doc['category'] = None
			doc['group'] = None
			catBalance = None
			if t['category_id'] is not None:
				doc['category'] = categories[t['category_id']]['name']
				doc['group'] = categories[t['category_id']]['group']
				catBalance = categories[t['category_id']]['balance']
			processTransaction(id, doc, catBalance, knownTransactions, init)
		docs.append(doc)

	# with open('known-docs.json', 'w') as f:
	# 	json.dump(docs, f, indent=4, sort_keys=True, ensure_ascii = True)
	# 	log.msg("Saving docs", file=f)

	with open('known-transactions.json', 'w') as f:
		json.dump(knownTransactions, f, indent=4, sort_keys=True, ensure_ascii = False)
		log.msg("Saving transactions", file=f)

	with open('budgeted-amounts.json', 'w') as f:
		json.dump(budgetedAmounts, f, indent=4, sort_keys=True, ensure_ascii = False)
		log.msg("Saving budgeted amounts", file=f)

# schedule the job - TODO check if frequency defined
schedule.every(settings['frequency']).minutes.do(job)
log.msg("Scheduling job", frequency=settings['frequency'])

# run
while True:
	schedule.run_pending()
	time.sleep(1)