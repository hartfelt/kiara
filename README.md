Kiara
=====

Kiara will hash your anime and add the episode to your anidb mylist.
It will also mark those files watched, and organize them nicely in folders.

Requirements
------------
Python 3.2 (or newer)
colorama (optional) - if you want colored output

Installation
------------
1. `sudo python3 setup.py install`
2. See /etc/kiararc for further instructions

Usage
-----
From `kiara -h`:

	usage: kiara [-h] [-w] [-o] [--copy] [--overwrite] [-c CONFIG]
	             [--find-duplicates] [--forget [FID [FID ...]]]
	             [FILE [FILE ...]]
	
	Do stuff with anime files and anidb.
	
	positional arguments:
	  FILE                  A file to do something with
	
	optional arguments:
	  -h, --help            show this help message and exit
	  -w, --watch           Mark all the files watched.
	  -o, --organize        Organize ALL THE FILES _o/
	  --copy                When organizing files, copy them instead of moving
	                        them.
	  --overwrite           When organizing files, always overwrite any existing
	                        files.
	  --skip-update         Skip updating file info from anidb, when the cached
	                        info is old. (missing info will still be fetched)
	  -c CONFIG, --config CONFIG
	                        Alternative config file to use.
	  --find-duplicates     Lists all episode for which you have more than one
	                        file
	  --forget [FID [FID ...]]
	                        Delete all info from the database (but not the file
	                        itself) about the files with the giver anidb file-id.
	                        (These are the numbers output by --find-duplicates
	  --brief               If nothing goes wrong, print only a single line for
	                        each file
	  --kill                Shut down the backend
