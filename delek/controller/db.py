"""Gestione del DB"""

from contextlib import contextmanager

from psycopg2 import connect
from psycopg2.extras import DictCursor
from psycopg2.extensions import AsIs

from flask import current_app, g


def quote(string):
    """Return the string enclosed in single quotes. Any single quote appearing
    in the string is escaped by doubling it according to SQL string constants
    syntax. Backslashes are escaped too."""
    return AsIs(string).getquoted()


def get_db():
    """Istanza DB"""
    if 'db' not in g:
        conn = connect(
            current_app.config['DB_PARAMS'],
            cursor_factory=DictCursor,
        )
        conn.set_session(autocommit=True)
        # Tutte le colonne timestamptz vanno interpretate/mostrate in ora
        # italiana, indipendentemente dal fuso del server (es. UTC su
        # Heroku): un solo punto per tutta l'app invece di 'at time zone'
        # sparso nelle query.
        with conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'Europe/Rome'")
        g.db = conn.cursor()

    return g.db


@contextmanager
def atomic():
    """Esegue un blocco di query come un'unica transazione: o vanno tutte a
    buon fine, o nessuna viene applicata. Da usare solo attorno a sequenze
    di scritture che devono riuscire/fallire insieme (es. le due righe di
    un movimento in partita doppia) — il resto dell'app resta in
    autocommit, non va cambiato il default globale della connessione."""
    dbi = get_db()
    conn = dbi.connection
    conn.autocommit = False
    try:
        yield dbi
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True


def close_db(error=None):
    """Close DB e rimuove from g"""
    dbi = g.pop('db', None)

    if error:
        print(error)
    if dbi is not None:
        dbi.close()


def init_app(app):
    """Main"""
    app.teardown_appcontext(close_db)
