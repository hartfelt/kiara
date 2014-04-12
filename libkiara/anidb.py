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

# Wrap outputting
OUTPUT = None
output_queue = list()
def output(*args):
	global OUTPUT
	try:
		if OUTPUT:
			OUTPUT(list(args))
	except TypeError: # OUTPUT is not a function.
		OUTPUT = None
		output_queue.append(args)
def set_output(o):
	global OUTPUT
	while output_queue:
		o(output_queue.pop(0))
	OUTPUT = o

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
	output('debug', '_',
		'--> %s' % (shit if command is not 'AUTH' else 'AUTH (hidden)'))
	sock.send(shit.encode('ascii'))
	
	# Receive shit
	while True:
		try:
			reply = sock.recv(1400).decode().strip()
		except socket.timeout:
			# Wait...
			output('status', 'socket_timeout')
			time.sleep(10)
			try:
				reply = sock.recv(1400).decode().strip()
			except socket.timeout:
				# Retry it only once. If this fails, anidb is either broken, or
				# blocking us
				output('error', 'socket_timeout_again')
				raise AbandonShip
		
		output('debug', '_', '<-- %s' % reply)
		if reply[0:3] == "555" or reply[6:9] == '555':
			output('error', 'banned', reply)
			raise AbandonShip
		return_tag, code, data = reply.split(' ', 2)
		if return_tag == tag:
			break
		else:
			output('debug', 'wrong_tag')
			# If this was a transmission error, or an anidb error, we will hit
			# a timeout and die...
	
	if code in DIE_MESSAGES:
		output('error', 'oh_no', code, data)
		raise AbandonShip
	if code in LATER_MESSAGES:
		output('error', 'anidb_busy')
		raise AbandonShip
	if code in REAUTH_MESSAGES:
		output('status', 'login_again', code, data)
		_connect(force=True)
		return _comm(command, **kwargs)
	return code, data

def ping(redirect):
	set_output(redirect.reply)
	_connect(needs_auth=False)
	code, reply = _comm('PING')
	if code == PONG:
		return True
	output('error', 'unexpected_reply', code, reply)
	return False

def _connect(force=False, needs_auth=True):
	global session_key, sock
	
	if not sock:
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.connect((config['host'], int(config['port'])))
		sock.settimeout(10)
	
	# If we have a session key, we assume that we are connected.
	if (not session_key and needs_auth) or force:
		output('status', 'logging_in')
		code, key = _comm(
			'AUTH',
			user=config['user'],
			protover=CLIENT_ANIDB_PROTOVER,
			client=CLIENT_NAME,
			clientver=CLIENT_VERSION,
			**{'pass': config['pass']} # We cannot use pass as a name :(
		)
		if code == LOGIN_ACCEPTED_OUTDATED_CLIENT:
			output('status', 'login_accepted_outdated_client')
		elif code == LOGIN_ACCEPTED:
			pass
		elif code in CLIENT_VERSION_OUTDATED:
			output('error', 'kiara_outdated')
			raise AbandonShip
		elif code in CLIENT_BANNED:
			output('error', 'kiara_banned')
			sys.exit()
		else:
			output('error', 'login_unexpected_return', code, key)
			raise AbandonShip
		
		session_key = key.split()[0]
		output('status', 'login_successful')
		output('debug', 'login_session_key', session_key)

def _type_map(ext):
	if ext in ['mpg', 'mpeg', 'avi', 'mkv', 'ogm', 'mp4', 'wmv']:
		return 'vid'
	if ext in ['ssa', 'sub', 'ass']:
		return 'sub'
	if ext in ['flac', 'mp3']:
		return 'snd'
	output('error', 'unknown_file_extension', str(ext))
	return None

def load_info(thing, redirect):
	set_output(redirect.reply)
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
		output('error', 'anidb_file_unknown')
	elif code == FILE:
		parts = reply.split('\n')[1].split('|')
		parts.reverse()
		thing.fid = int(parts.pop())
		thing.aid = int(parts.pop())
		thing.mylist_id = int(parts.pop())
		thing.crc32 = parts.pop()
		thing.file_type = _type_map(parts.pop())
		output('debug', 'file_type', thing.file_type)
		thing.added = parts.pop() == '1'
		thing.watched = parts.pop() == '1'
		thing.anime_total_eps = int(parts.pop())
		thing.anime_type = parts.pop()
		thing.anime_name = parts.pop()
		thing.ep_no = parts.pop()
		thing.group_name = parts.pop()
		thing.updated = datetime.now()
		thing.dirty = True

def add(thing, redirect):
	set_output(redirect.reply)
	_connect()
	
	code, reply = _comm('MYLISTADD',
		fid=str(thing.fid),
		state='1')
	if code == MYLIST_ENTRY_ADDED:
		thing.mylist_id = reply.split('\n')[1]
		thing.added = True
		thing.dirty = True
		output('success', 'file_added')
	elif code == FILE_ALREADY_IN_MYLIST:
		thing.mylist_id = reply.split('\n')[1].split('|')[0]
		thing.added = True
		thing.dirty = True
		output('success', 'file_added')
	else:
		output('error', 'unexpected_reply', code, reply)

def watch(thing, redirect):
	set_output(redirect.reply)
	_connect()
	
	code, reply = _comm('MYLISTADD',
		lid=str(thing.mylist_id),
		edit='1', state='1', viewed='1')
	if code == MYLIST_ENTRY_EDITED:
		thing.watched = True
		thing.dirty = True
		output('success', 'file_marked_watched')
	else:
		output('error', 'unexpected_reply', code, reply)
