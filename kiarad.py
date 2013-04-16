#!/usr/bin/env python3

import os.path
import sys
import argparse
from datetime import datetime, timedelta
import socketserver

import ed2khash
import database
import anidb

# Default confg values.
config = {
	'host': 'api.anidb.net',
	'port': '9000',
	'session': '~/.kiara.session',
	'database': '~/.kiara.db',
}
anidb.config = config

def config_items(file):
	for line in map(lambda s: s.strip(), file.readlines()):
		if line.startswith('#') or not line:
			continue
		yield line.split(None, 1)

parser = argparse.ArgumentParser(
	description='Kiara backend')
parser.add_argument('-c', '--config',
	action='store', dest='config', type=argparse.FileType('r'),
	help='Alternative config file to use.')

args = parser.parse_args()

# Read config.
try:
	with open('/etc/kiararc', 'rb') as fp:
		config.update(config_items(fp))
except: pass
try:
	with open(os.path.expanduser('~/.kiararc'), 'r') as fp:
		config.update(config_items(fp))
except: pass
if args.config:
	config.update(config_items(args.config))

config_err = False
for key in 'host port user pass database session'.split():
	if not key in config:
		print('ERROR: Missing config variable:', key)
		config_err = True
if config_err:
	sys.exit(-1)

# Connect the database.
database.connect(os.path.expanduser(config['database']), config['user'])

# Define a dump object to pass around.
class KiaraFile(object):
	def __init__(self, name):
		self.file = open(name, 'rb')
		self.file_name = name
		self.name = os.path.basename(name)
		self.size = os.path.getsize(name)
		
		self.dirty = False # Should this be saved.
		self.updated = None
		self.in_anidb = True
		
		self.hash = None
		self.watched = False
		self.fid = None
		self.mylist_id = None
		self.aid = None
		self.crc32 = None
		
		self.anime_total_eps = None
		self.anime_name = None
		self.anime_type = None
		self.ep_no = None
		self.group_name = None
		
		self.added = False
	
	def misses_info(self):
		return (
			self.fid == None or
			self.mylist_id == None or
			self.aid == None or
			self.crc32 == None or
			self.anime_total_eps == None or
			self.anime_name == None or
			self.anime_type == None or
			self.ep_no == None or
			self.group_name == None)
	
	def __str__(self):
		parts = [self.name]
		if self.hash:
			parts.append(self.hash)
		if self.dirty:
			parts.append('(unsaved)')
		return ' '.join(parts)

class Handler(socketserver.BaseRequestHandler):
	def reply(self, message):
		self.write(message + '\n')
	
	def write(self, message):
		self.request.send(bytes(message, 'UTF-8'))
	
	def handle(self):
		data = self.request.recv(1024).strip().decode('UTF-8')
		
		if data == 'ping':
			if anidb.ping(self):
				self.reply('pong')
			else:
				self.reply('No answer :(')
				sys.exit(1)
		
		else:
			act, file = data.split(' ', 1)
			file = KiaraFile(file)
			
			# Load file info.
			database.load(file)
			if not file.hash:
				self.reply('Hashing ' + file.name)
				file.hash = ed2khash.hash(file.file)
				database.load(file)
			
			if file.misses_info() or \
					file.updated < datetime.now() - timedelta(days=7):
				anidb.load_info(file, self)
			
			if not file.fid:
				print('!!! File is unknown to anidb. Will not process further')
			else:
				if (not file.added) and 'a' in act:
					anidb.add(file, self)
				
				if not file.watched and 'w' in act:
					anidb.watch(file, self)
				
				if 'o' in act:
					self.reply('TODO: organize ' + str(file))
				
				database.save(file)
			
		self.request.sendall(bytes('---end---', 'UTF-8'))

try:
	os.remove(os.path.expanduser(config['session']))
except: pass
socketserver.UnixStreamServer(
	os.path.expanduser(config['session']), Handler).serve_forever()
