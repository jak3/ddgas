""" Gestione del DB """
from psycopg2 import connect
from psycopg2.extras import DictCursor
from psycopg2.extensions import AsIs

from flask import current_app, g


def quote(string):
    """ Return the string enclosed in single quotes. Any single quote appearing
    in the string is escaped by doubling it according to SQL string constants
    syntax. Backslashes are escaped too. """
    return AsIs(string).getquoted()


def get_db():
    """ Istanza DB """
    if 'db' not in g:
        conn = connect(
            current_app.config['DB_PARAMS'],
            cursor_factory=DictCursor,
        )
        conn.set_session(autocommit=True)
        g.db = conn.cursor()

    return g.db


def close_db(error=None):
    """ Close DB e rimuove from g """
    dbi = g.pop('db', None)

    if error:
        print(error)
    if dbi is not None:
        dbi.close()


def init_app(app):
    """ Main """
    app.teardown_appcontext(close_db)
