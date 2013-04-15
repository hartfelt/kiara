import socket
import os, sys
from datetime import datetime, timedelta
import time

CLIENT_NAME = "kiara"
CLIENT_VERSION = "4"
CLIENT_ANIDB_PROTOVER = "3"

LOGIN_ACCEPTED = '200'
LOGIN_ACCEPTED_OUTDATED_CLIENT = '201'
LOGGED_OUT = '203'
MYLIST_ENTRY_ADDED = '210'
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

# This will get overridden from kiara.py
config = None
session_key = None
sock = None

message_interval = timedelta(seconds=4)
next_message = datetime.now()

def _comm(command, **kwargs):
	global next_message, session_key
	assert sock != None
	
	wait = (next_message - datetime.now()).total_seconds()
	if wait > 0:
		time.sleep(wait)
	next_message = datetime.now() + message_interval
	
	# Send shit.
	sock.send((command + " " + "&".join(
		map(lambda k: "%s=%s" % (k, kwargs[k]), kwargs)
	)).encode('ascii'))
	
	# Receive shit
	reply = sock.recv(1400).decode().strip()
	print('>>>', reply)
	if reply[0:3] == "555":
		print("We got banned :(")
		print(reply)
		print("Try again in 30 minutes")
		sys.exit(-2)
	
	code, data = reply.split(' ', 1)
	if code in DIE_MESSAGES:
		print("OH NOES", code, data)
		sys.exit(-1)
	if code in LATER_MESSAGES:
		print("AniDB is busy, please try again later")
		sys.exit(-1)
	if code in REAUTH_MESSAGES:
		print('We need to log in again (%s %s)' % (code, data))
		session_key = None
		_delete_session()
		_connect()
		return _comm(command, **kwargs)
	return code, data

def ping():
	_connect()
	code, reply = _comm('PING', s=session_key)
	if code == PONG:
		return True
	print('Unexpected reply to PING:', code, reply)
	return False

def _delete_session():
	if os.path.isfile(os.path.expanduser(config['session'])):
		os.remove(os.path.expanduser(config['session']))
	else:
		print('would have deleted session file, but it is gone')

def _connect():
	global session_key, sock
	
	if not sock:
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.connect((config['host'], int(config['port'])))
		sock.settimeout(10)
	
	if not session_key:
		# Load session key from file
		try:
			with open(os.path.expanduser(config['session']), 'r') as fp:
				session_key = fp.read().strip()
		except IOError:
			pass
		except Exception as e:
			print('we caught exception:', type(e), repr(e), e)
	
	# If we have a session key, we assume that we are connected.
	if not session_key:
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
			sys.exit()
		elif code in CLIENT_BANNED:
			print("kiara is banned from AniDB :(")
			print("(Your AniDB user should be ok)")
			sys.exit()
		else:
			print(
				"Unexpected return code to AUTH command. Please show " +
				"this to the delevopers of kiara:"
			)
			print(code, reply)
			sys.exit()
		
		session_key = key.split()[0]
		print("Login successful, we got session key %s" % session_key)
	
	# Save the session key for future use.
	if session_key:
		with open(os.path.expanduser(config['session']), 'w') as fp:
			fp.write(session_key)
	else:
		_delete_session()

def load_info(thing):
	print('loading info')
	_connect()
	lookup = {
		'fmask': '0808000000',
		'amask': '80808040',
		's': session_key,
	}
	if thing.fid:
		lookup['fid'] = thing.fid
	else:
		lookup['size'] = thing.size
		lookup['ed2k'] = thing.hash
		
	print('lookup', lookup)
	code, reply = _comm('FILE', **lookup)
	print(code, reply)
	# fmask=0808000000 amask=80808040

def add(thing):
	_connect()
	print('TODO: add', thing)

def watch(thing):
	_connect()
	print('TODO: watch', thing)
