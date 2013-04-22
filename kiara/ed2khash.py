#!/usr/bin/env python3

''' implementation of ed2k-hashing in python. original code stolen from
http://www.radicand.org/blog/orz/2010/2/21/edonkey2000-hash-in-python/'''

import hashlib
import os.path
from functools import reduce

_md4 = hashlib.new('md4').copy

def _chuncks(f):
	while True:
		x = f.read(9728000)
		if x:
			yield x
		else:
			return

def _md4_hash(data):
	m = _md4()
	m.update(data)
	return m

def hash(file):
	""" Returns the ed2k hash of the given file. """
	hashes = [_md4_hash(data) for data in _chuncks(file)]
	if len(hashes) == 1:
		return hashes[0].hexdigest()
	else:
		return _md4_hash(
			reduce(lambda a, b: a + b.digest(), hashes, b'')
		).hexdigest()

def link(file):
	""" Returns the ed2k link of the given file. """
	return "ed2k://|file|%s|%d|%s|" % (
		os.path.basename(file.name),
		os.path.getsize(file.name),
		hash(file)
	)
