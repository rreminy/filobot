import os
import sys
import logging
from peewee import SqliteDatabase

logger = logging.getLogger('peewee')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.WARNING)

db_path = os.path.dirname(os.path.realpath(sys.argv[0])) + os.sep + os.path.join('data', 'filobot.db')
db = SqliteDatabase(db_path, pragmas={'foreign_keys': 1})
