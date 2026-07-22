''' ipython helper, to work with psycopg2 '''
import psycopg2
from psycopg2 import extras

conn = psycopg2.connect(dbname='delek', cursor_factory=extras.DictCursor)
curs = conn.cursor()
