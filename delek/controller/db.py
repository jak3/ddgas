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


def column_names_placeholders(inputs):
    """Da un dict {colonna: valore} genera i due frammenti SQL, già tra
    parentesi, per costruire INSERT INTO t {column_names} VALUES
    {placeholders} oppure UPDATE t SET {column_names} = {placeholders}
    (sintassi Postgres di assegnamento multiplo su riga). Es. con
    {'nome': 'Mario', 'email': 'm@x.it'} ritorna
    ('(nome, email)', '(%s, %s)'). tuple(inputs.values()) va passato come
    parametri nello stesso ordine.

    Sostituisce l'idioma ripetuto in vari controller
    str(tuple(cn for cn in inputs)).replace("'", ''): fragile (dipende dal
    repr di un tuple, si rompe se una chiave contiene un apice) e
    incoerente (a seconda del punto le parentesi erano già incluse nel
    valore o aggiunte dalla query stessa)."""
    column_names = '(' + ', '.join(inputs) + ')'
    placeholders = '(' + ', '.join('%s' for _ in inputs) + ')'
    return column_names, placeholders


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
