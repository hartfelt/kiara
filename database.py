import sqlite3

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
			size integer
		)
	''')
	c.execute('''
		CREATE TABLE IF NOT EXISTS file_status (
			hash text,
			size integer,
			username text,
			watched boolean
		);
	''')
	conn.commit()

def load(thing):
	c = conn.cursor()
	
	# Lookup thing by name
	if not thing.hash:
		c.execute('''
			SELECT hash
			FROM file
			WHERE filename = ? AND size = ?
		''', (thing.name, thing.size))
		r = c.fetchone()
		if r:
			thing.hash = r[0]
	
	# Lookup thing by hash
	if thing.hash:
		c.execute('''
			SELECT filename
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
		
		# Look up the status.
		c.execute('''
			SELECT watched
			FROM file_status
			WHERE hash = ? AND size = ? AND username = ?
		''', (thing.hash, thing.size, username))
		r = c.fetchone()
		if r:
			thing.added = True
			thing.watched = bool(r[0])

def save(thing):
	if thing.dirty:
		c = conn.cursor()
		c.execute('''
			DELETE FROM file
			WHERE hash = ? AND size = ?
		''', (thing.hash, thing.size))
		c.execute('''
			INSERT INTO file (hash, filename, size)
			VALUES (?, ?, ?)
		''', (thing.hash, thing.name, thing.size))
		
		c.execute('''
			DELETE FROM file_status
			WHERE hash = ? AND size = ? AND username = ?
		''', (thing.hash, thing.size, username))
		if thing.added:
			c.execute('''
				INSERT INTO file_status (hash, size, username, watched)
				VALUES (?, ?, ?, ?)
			''', (thing.hash, thing.size, username, thing.watched))
			
		conn.commit()
