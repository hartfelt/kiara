import os.path
import sys
import shutil
from datetime import datetime, timedelta
import socketserver
import socket # for the exceptions
from libkiara import ed2khash, database, anidb, AbandonShip

config = {}

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
		self.type = None
		
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
			self.file_type == None or
			self.anime_total_eps == None or
			self.anime_name == None or
			self.anime_type == None or
			self.ep_no == None or
			self.group_name == None)
	
	def is_movie(self):
		return (
			self.anime_type == 'Movie' or
			self.anime_type == 'OVA' and self.anime_total_eps == 1 or
			self.anime_type == 'Web' and self.anime_total_eps == 1)
	
	def __str__(self):
		parts = [self.name]
		if self.hash:
			parts.append(self.hash)
		if self.dirty:
			parts.append('(unsaved)')
		return ' '.join(parts)

def makedirs(path):
	parts = os.path.abspath(path).split(os.path.sep)
	path = '/'
	while parts:
		path = os.path.join(path, parts.pop(0))
		if not os.path.exists(path):
			os.makedirs(path)

def rmdirp(path):
	while path:
		if os.listdir(path) == []:
			yield ['status', 'removing_empty_dir', path]
			os.rmdir(path)
			path = os.path.dirname(path)
		else:
			return
	
def pad(length, num):
	try:
		int(num)
		return "0" * max(0, (length - len(num))) + num
	except ValueError:
		return num

class Handler(socketserver.BaseRequestHandler):
	def __init__(self, *args, **kwargs):
		self.queued_messages = []
		return super().__init__(*args, **kwargs)
	
	def reply(self, message, catch_fails=True):
		if type(message) == tuple:
			message = list(message)
		if type(message) == list:
			message = '\n'.join(message)
		self.write(message + '\n', catch_fails)
	
	def write(self, message, catch_fails=True):
		try:
			self.request.send(bytes(message+'\n', 'UTF-8'))
		except socket.error:
			if catch_fails:
				self.queued_messages.append(message)
	
	def handle(self):
		while self.queued_messages:
			self.reply(self.queued_messages.pop(0), False)
		data = self.request.recv(1024).strip().decode('UTF-8')
		
		act, file_name = data.split(' ', 1)
		if act == '-':
			# Non-file related commands
			if file_name == 'ping':
				if anidb.ping(self):
					self.reply(['success', 'anidb_ping_ok'])
				else:
					self.reply(['error', 'anidb_ping_error'])
			
			if file_name == 'dups':
				dups = False
				for line in database.find_duplicates():
					dups = True
					self.reply(line)
				if not dups:
					self.reply(['success', 'dups_none'])
			
			if file_name.startswith('forget'):
				for fid in file_name.split(' ')[1:]:
					for line in database.forget(int(fid)):
						self.reply(line)
			
			if file_name == 'kill':
				self.reply(['status', 'backend_shutting_down'])
				self.shutdown()
		else:
			try:
				# File related commands
				file = KiaraFile(file_name)
				
				# Load file info.
				database.load(file)
				if not file.hash:
					self.reply(['status', 'hashing_file', file.name])
					file.hash = ed2khash.hash(file.file)
					database.load(file)
				
				if file.misses_info() or not file.updated or \
						'u' in act and \
						file.updated < datetime.now() - timedelta(days=7):
					anidb.load_info(file, self)
				
				if not file.fid:
					self.reply(['error', 'anidb_file_unknown'])
				else:
					if (not file.added) and 'a' in act:
						self.reply(['status', 'anidb_adding_file',
							file.anime_name, str(file.ep_no)])
						anidb.add(file, self)
					
					if not file.watched and 'w' in act:
						self.reply(['status', 'anidb_marking_watched',
							file.anime_name, str(file.ep_no)])
						anidb.watch(file, self)
					
					if 'o' in act:
						anime_name = file.anime_name.replace('/', '_')
						dir = os.path.join(os.path.expanduser((
							config['basepath_movie']
							if file.is_movie()
							else config['basepath_series'])), anime_name)
						self.reply(['debug', 'file_type_location',
							file.anime_type, dir])
						
						makedirs(os.path.normpath(dir))
						new_name = None
						if file.anime_total_eps == "1":
							new_name = "[%s] %s [%s]%s" % (
								file.group_name, anime_name, file.crc32,
								os.path.splitext(file_name)[1])
						else:
							new_name = "[%s] %s - %s [%s]%s" % (
								file.group_name, anime_name,
								pad(
									len(str(file.anime_total_eps)),
									str(file.ep_no)),
								file.crc32, os.path.splitext(file_name)[1])
						new_path = os.path.join(dir, new_name)
						
						if file_name == new_path:
							self.reply(['status', 'file_already_organized',
								new_name])
						else:
							if os.path.isfile(new_path) and not 'x' in act:
								self.reply(['error', 'file_exists', new_path])
							else:
								if 'c' in act:
									shutil.copyfile(file_name, new_path)
									self.reply(['success', 'file_copied',
										file_name, new_path])
								else:
									shutil.move(file_name, new_path)
									self.reply(['success', 'file_moved',
										file_name, new_path])
								file.name = new_name
								file.dirty = True
						
							for r in rmdirp(os.path.dirname(file_name)):
								self.reply(r)
						
					database.save(file)
			except SystemExit as e:
				self.request.sendall(bytes('---end---', 'UTF-8'))
				self.request.close()
				sys.exit(status)
				
			except AbandonShip:
				self.reply(['error', 'abandon_ship'])
				# Ignore the actual error, the connection will be closed now
			
		self.request.sendall(bytes('---end---', 'UTF-8'))

def serve(cfg):
	global config
	config = cfg
	anidb.config = config
	database.connect(os.path.expanduser(config['database']), config['user'])
	
	try:
		os.remove(os.path.expanduser(config['session']))
	except: pass
	
	run = [True]
	def killer(r):
		r[0] = False
	
	class ActualHandler(Handler):
		def __init__(self, *args, **kwargs):
			self.shutdown = lambda: killer(run)
			return super().__init__(*args, **kwargs)
	
	server = socketserver.UnixStreamServer(
		os.path.expanduser(config['session']), ActualHandler)
	while run[0]:
		server.handle_request()
