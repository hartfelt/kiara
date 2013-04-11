#!/usr/bin/env python3

import sqlite3

conn = None

def connect(database):
	global conn
	conn = sqlite3.connect(database)
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
			added boolean,
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
		if r:
			if r[0] != thing.name:
				print('Filename in database have changed')
				thing.dirty = True
		else:
			# New thing
			thing.dirty = True

def save(thing):
	if thing.dirty:
		c = conn.cursor()
		c.execute('''
			DELETE FROM file
			WHERE hash = ?
		''', (thing.hash,))
		c.execute('''
			INSERT INTO file (hash, filename, size)
			VALUES (?, ?, ?)
		''', (thing.hash, thing.name, thing.size))
		conn.commit()
