#!/usr/bin/env python3

import os.path
import sys
import argparse

import ed2khash
import database

# Default confg values.
config = {
	'host': 'api.anidb.net',
	'port': '9000',
	'session': '~/.kiara.session',
	'database': '~/.kiara.db',
}
def config_items(file):
	for line in map(lambda s: s.strip(), file.readlines()):
		if line.startswith('#') or not line:
			continue
		yield line.split(None, 1)

parser = argparse.ArgumentParser(
	description='Do stuff with anime files and anidb.')
parser.add_argument('-w', '--watch',
	action='store_true', dest='watch',
	help='Mark all the files watched.')
parser.add_argument('-o', '--organize',
	action='store_true', dest='organize',
	help='Organize ALL THE FILES _o/')
parser.add_argument('-c', '--config',
	action='store', dest='config', type=argparse.FileType('r'),
	help='Alternative config file to use.')
parser.add_argument('files',
	metavar='FILE', type=argparse.FileType('rb'), nargs='+',
	help='a file to do something with')

args = parser.parse_args()

# Read config.
try:
	with open('/etc/kiararc', 'r') as fp:
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
database.connect(os.path.expanduser(config['database']))

# Define a dump object to pass around.
class KiaraFile(object):
	def __init__(self, file):
		self.file = file
		self.name = os.path.basename(file.name)
		self.size = os.path.getsize(file.name)
		
		self.dirty = False # Should this be saved.
		self.hash = None
	
	def __str__(self):
		parts = [self.name]
		if self.hash:
			parts.append(self.hash)
		if self.dirty:
			parts.append('(unsaved)')
		return ' '.join(parts)

# OK, run over the files.
files = [KiaraFile(file) for file in args.files]

# Load the info we already have on that file and create the missing
# stuff.
for file in files:
	database.load(file)
	if not file.hash:
		print('Hashing', file.name)
		file.hash = ed2khash.hash(file.file)
		database.load(file)
	print(file)
	
	database.save(file)
