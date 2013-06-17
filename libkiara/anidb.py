from datetime import datetime, timedelta
import os
import random
import socket
import string
import sys
import time
from libkiara import AbandonShip

CLIENT_NAME = "kiara"
CLIENT_VERSION = "4"
CLIENT_ANIDB_PROTOVER = "3"

LOGIN_ACCEPTED = '200'
LOGIN_ACCEPTED_OUTDATED_CLIENT = '201'
LOGGED_OUT = '203'
MYLIST_ENTRY_ADDED = '210'
FILE = '220'
PONG = '300'
FILE_ALREADY_IN_MYLIST = '310'
MYLIST_ENTRY_EDITED = '311'
NO_SUCH_FILE = '320'
NOT_LOGGED_IN = '403'
LOGIN_FAILED = '500'
LOGIN_FIRST = '501'
ACCESS_DENIED = '502'
CLIENT_VERSION_OUTDATED = '503'
CLIENT_BANNED = '504'
ILLEGAL_INPUT = '505'
INVALID_SESSION = '506'
BANNED = '555'
UNKNOWN_COMMAND = '598'
INTERNAL_SERVER_ERROR = '600'
OUT_OF_SERVICE = '601'
SERVER_BUSY = '602'

DIE_MESSAGES = [
	BANNED, ILLEGAL_INPUT, UNKNOWN_COMMAND,
	INTERNAL_SERVER_ERROR, ACCESS_DENIED
]
LATER_MESSAGES = [OUT_OF_SERVICE, SERVER_BUSY]
REAUTH_MESSAGES = [LOGIN_FIRST, INVALID_SESSION]

# This will get overridden from kiarad.py
config = None
session_key = None
sock = None

# anidb specifies a hard limit that no more than one message every 2 seconds
# may me send, and a soft one at one message every 4 seconds over an 'extended
# period'. 3 seconds is... faster than 4...
message_interval = timedelta(seconds=3)
next_message = datetime.now()

def tag_gen(length=5):
	""" Makes random strings for use as tags, so messages from anidb will not
	get mixed up. """
	return "".join([
		random.choice(string.ascii_letters)
		for _ in range(length)])

def _comm(command, **kwargs):
	global next_message, session_key
	assert sock != None
	
	wait = (next_message - datetime.now()).total_seconds()
	if wait > 0:
		time.sleep(wait)
	next_message = datetime.now() + message_interval
	
	# Add a tag
	tag = tag_gen()
	kwargs['tag'] = tag
	# And the session key, if we have one
	if session_key:
		kwargs['s'] = session_key
	# Send shit.
	shit = (command + " " + "&".join(
		map(lambda k: "%s=%s" % (k, kwargs[k]), kwargs)))
	if 'debug' in config:
		print('-->', (shit if command is not 'AUTH' else 'AUTH (hidden)'))
	sock.send(shit.encode('ascii'))
	
	# Receive shit
	while True:
		try:
			reply = sock.recv(1400).decode().strip()
		except socket.timeout:
			# Wait...
			print('We got a socket timeout... hang on')
			time.sleep(10)
			try:
				reply = sock.recv(1400).decode().strip()
			except socket.timeout:
				# Retry it only once. If this fails, anidb is either broken, or
				# blocking us
				print('Another timeout... bailing out')
				raise AbandonShip
		
		if 'debug' in config:
			print('<--', reply)
		if reply[0:3] == "555" or reply[6:9] == '555':
			print("We got banned :(")
			print(reply)
			print("Try again in 30 minutes")
			raise AbandonShip
		return_tag, code, data = reply.split(' ', 2)
		if return_tag == tag:
			break
		else:
			print('We got a message with the wrong tag... we have probably '
				'missed the previous message. I\'ll try again.')
			# If this was a transmission error, or an anidb error, we will hit
			# a timeout and die...
	
	if code in DIE_MESSAGES:
		print("OH NOES", code, data)
		raise AbandonShip
	if code in LATER_MESSAGES:
		print("AniDB is busy, please try again later")
		raise AbandonShip
	if code in REAUTH_MESSAGES:
		print('We need to log in again (%s %s)' % (code, data))
		_connect(force=True)
		return _comm(command, **kwargs)
	return code, data

def ping(redirect):
	sys.stdout = redirect
	_connect(needs_auth=False)
	code, reply = _comm('PING')
	if code == PONG:
		return True
	print('Unexpected reply to PING:', code, reply)
	return False
	sys.stdout = sys.__stdout__

def _connect(force=False, needs_auth=True):
	global session_key, sock
	
	if not sock:
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.connect((config['host'], int(config['port'])))
		sock.settimeout(10)
	
	# If we have a session key, we assume that we are connected.
	if (not session_key and needs_auth) or force:
		print('Logging in')
		code, key = _comm(
			'AUTH',
			user=config['user'],
			protover=CLIENT_ANIDB_PROTOVER,
			client=CLIENT_NAME,
			clientver=CLIENT_VERSION,
			**{'pass': config['pass']} # We cannot use pass as a name :(
		)
		if code == LOGIN_ACCEPTED_OUTDATED_CLIENT:
			print("Login accepted, but your copy of kiara is outdated.")
			print("Please consider updating it.")
		elif code == LOGIN_ACCEPTED:
			pass
		elif code in CLIENT_VERSION_OUTDATED:
			print("kiara have become outdated :(")
			print("check the interwebs for an updated version")
			raise AbandonShip
		elif code in CLIENT_BANNED:
			print("kiara is banned from AniDB :(")
			print("(Your AniDB user should be ok)")
			sys.exit()
		else:
			print(
				"Unexpected return code to AUTH command. Please show " +
				"this to the delevopers of kiara:"
			)
			print(code, key)
			raise AbandonShip
		
		session_key = key.split()[0]
		print("Login successful, we got session key %s" % session_key)

def _type_map(ext):
	if ext in ['mpg', 'mpeg', 'avi', 'mkv', 'ogm', 'mp4']:
		return 'vid'
	if ext in ['ssa', 'sub']:
		return 'sub'
	print("!!! UNKNOWN FILE EXTENSION:", ext)
	return None

def load_info(thing, redirect):
	sys.stdout = redirect
	_connect()
	
	lookup = {
		'fmask': '48080100a0',
		'amask': '90808040',
	}
	if thing.fid:
		lookup['fid'] = thing.fid
	else:
		lookup['size'] = thing.size
		lookup['ed2k'] = thing.hash
	
	code, reply = _comm('FILE', **lookup)
	if code == NO_SUCH_FILE:
		print('File not found :(')
	elif code == FILE:
		parts = reply.split('\n')[1].split('|')
		parts.reverse()
		thing.fid = int(parts.pop())
		thing.aid = int(parts.pop())
		thing.mylist_id = int(parts.pop())
		thing.crc32 = parts.pop()
		thing.file_type = _type_map(parts.pop())
		if 'debug' in config:
			print('file type is', thing.file_type)
		thing.added = parts.pop() == '1'
		thing.watched = parts.pop() == '1'
		thing.anime_total_eps = int(parts.pop())
		thing.anime_type = parts.pop()
		thing.anime_name = parts.pop()
		thing.ep_no = parts.pop()
		thing.group_name = parts.pop()
		thing.updated = datetime.now()
		thing.dirty = True
	
	sys.stdout = sys.__stdout__

def add(thing, redirect):
	sys.stdout = redirect
	_connect()
	
	code, reply = _comm('MYLISTADD',
		fid=str(thing.fid),
		state='1')
	if code == MYLIST_ENTRY_ADDED:
		thing.mylist_id = reply.split('\n')[1]
		thing.added = True
		thing.dirty = True
		print('File added')
	elif code == FILE_ALREADY_IN_MYLIST:
		thing.mylist_id = reply.split('\n')[1].split('|')[0]
		thing.added = True
		thing.dirty = True
		print('File added')
	else:
		print('UNEXPECTED REPLY:', code, reply)
	
	sys.stdout = sys.__stdout__

def watch(thing, redirect):
	sys.stdout = redirect
	_connect()
	
	code, reply = _comm('MYLISTADD',
		lid=str(thing.mylist_id),
		edit='1', state='1', viewed='1')
	if code == MYLIST_ENTRY_EDITED:
		thing.watched = True
		thing.dirty = True
		print('File marked watched')
	else:
		print('UNEXPECTED REPLY:', code, reply)
	
	sys.stdout = sys.__stdout__
