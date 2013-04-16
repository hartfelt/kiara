import sqlite3
from datetime import datetime

conn, username = None, None

def connect(database, user):
	global conn, username
	conn = sqlite3.connect(database)
	username = user
	
	c = conn.cursor()
	
	# Create tables if they do not exist.
	c.execute('''
		CREATE TABLE IF NOT EXISTS file (
			hash text,
			filename text,
			size integer,
			fid integer,
			aid integer,
			crc32 string,
			ep_no string,
			group_name string,
			updated string
		)
	''')
	c.execute('''
		CREATE TABLE IF NOT EXISTS file_status (
			fid integer,
			username text,
			watched boolean,
			mylist_id integer,
			updated string
		);
	''')
	c.execute('''
		CREATE TABLE IF NOT EXISTS anime (
			aid integer,
			total_eps integer,
			name integer,
			type string,
			updated string
		);
	''')
	conn.commit()

def load(thing):
	c = conn.cursor()
	
	# Lookup thing by name
	if not thing.hash:
		c.execute('''
			SELECT hash, fid, aid, crc32, ep_no, group_name, updated
			FROM file
			WHERE filename = ? AND size = ?
		''', (thing.name, thing.size))
		r = c.fetchone()
		if r:
			thing.hash, thing.fid, thing.aid, \
				thing.crc32, thing.ep_no, thing.group_name = r[:6]
			thing.updated = datetime.strptime(r[6], '%Y-%m-%d %H:%M:%S.%f')
	
	# Lookup thing by hash
	if thing.hash:
		c.execute('''
			SELECT filename, fid, aid, crc32, ep_no, group_name, updated
			FROM file
			WHERE hash = ? AND size = ?
		''', (thing.hash, thing.size))
		r = c.fetchone()
		if not r:
			# This is a new thing
			thing.dirty = True
			return
		
		if r[0] != thing.name:
			print('Filename in database have changed')
			thing.dirty = True
		thing.fid, thing.aid, thing.crc32, thing.ep_no, thing.group_name \
			= r[1:6]
		thing.updated = datetime.strptime(r[6], '%Y-%m-%d %H:%M:%S.%f')
		
	if thing.fid:
		# Look up the status.
		c.execute('''
			SELECT watched, mylist_id, updated
			FROM file_status
			WHERE fid = ? AND username = ?
		''', (thing.fid, username))
		r = c.fetchone()
		if r:
			thing.mylist_id = r[0]
			thing.added = bool(r[0])
			thing.watched = bool(r[1])
			thing.updated = min(
				thing.updated,
				datetime.strptime(r[2], '%Y-%m-%d %H:%M:%S.%f'))
	
	if thing.aid:
		c.execute('''
			SELECT total_eps, name, type, updated
			FROM anime
			WHERE aid = ?
		''', (thing.aid, ))
		r = c.fetchone()
		if r:
			thing.anime_total_eps, thing.anime_name, thing.anime_type = r[:3]
			thing.updated = min(
				thing.updated,
				datetime.strptime(r[3], '%Y-%m-%d %H:%M:%S.%f'))

def save(thing):
	if thing.dirty:
		c = conn.cursor()
		c.execute('''
			DELETE FROM file
			WHERE hash = ? AND size = ? OR fid = ?
		''', (thing.hash, thing.size, thing.fid))
		c.execute('''
			INSERT INTO file (
				hash, filename, size, fid, aid, crc32, ep_no,
				group_name, updated)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		''', (
			thing.hash, thing.name, thing.size, thing.fid, thing.aid,
			thing.crc32, thing.ep_no, thing.group_name, str(thing.updated)))
		
		c.execute('''
			DELETE FROM file_status
			WHERE fid = ? AND username = ?
		''', (thing.fid, username))
		if thing.added:
			c.execute('''
				INSERT INTO file_status (
					fid, username, watched, mylist_id, updated)
				VALUES (?, ?, ?, ?, ?)
			''', (
				thing.fid, username, thing.watched, thing.mylist_id,
				str(thing.updated)))
		
		c.execute('''
			DELETE FROM anime
			WHERE aid = ?
		''', (thing.aid, ))
		c.execute('''
			INSERT INTO anime (aid, total_eps, name, type, updated)
			VALUES (?, ?, ?, ?, ?)
		''', (
			thing.aid, thing.anime_total_eps, thing.anime_type,
			thing.anime_name, str(thing.updated)))
		
		conn.commit()
