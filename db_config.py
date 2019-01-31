
import os, sys
from sqlalchemy.engine.url import URL

sqlite_db = {
	'drivername': 'sqlite',
	'username': None,
	'password': None,
	'host': None,
	'port': None,
	'database': 'database.db'
}

db_url = URL(**sqlite_db)
