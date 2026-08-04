import os
import re

import psycopg2
import pytest
from werkzeug.security import generate_password_hash

from delek import create_app

TEST_DB = 'delek_test'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_SQL = os.path.join(ROOT, 'data', 'db', 'pg', 'schema.sql')
DB_HOST = os.environ.get('DELEK_DB_HOST', '127.0.0.1')


def _connect(dbname):
    conn = psycopg2.connect(dbname=dbname, host=DB_HOST)
    conn.autocommit = True
    return conn


@pytest.fixture(scope='session', autouse=True)
def _test_database():
    """Ricrea da zero delek_test una volta per sessione di test, dallo
    schema.sql "vero" (i DROP TABLE IF EXISTS in testa, che non vanno mai
    lanciati contro il DB live, qui sono esattamente quello che serve per
    un DB usa-e-getta). Mai lo stesso DB usato per lo sviluppo locale
    (delek), per non modificare dati reali."""
    admin = _connect('postgres')
    with admin.cursor() as cur:
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
            " WHERE datname = %s AND pid <> pg_backend_pid()",
            (TEST_DB,),
        )
        cur.execute('DROP DATABASE IF EXISTS {0}'.format(TEST_DB))
        cur.execute('CREATE DATABASE {0}'.format(TEST_DB))
    admin.close()

    conn = _connect(TEST_DB)
    with conn.cursor() as cur, open(SCHEMA_SQL) as f:
        cur.execute(f.read())
    conn.close()
    yield


@pytest.fixture(autouse=True)
def _clean_db():
    """Isola i test l'uno dall'altro: droppa le tabelle listino_N /
    ordine_in_corso_N create dinamicamente (non fanno parte dello schema
    base) e svuota le tabelle popolate dai fixture, prima di ogni test."""
    conn = _connect(TEST_DB)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
              AND (tablename LIKE 'listino\\_%'
                   OR tablename LIKE 'ordine\\_in\\_corso\\_%')
        """)
        for (name,) in cur.fetchall():
            cur.execute('DROP TABLE IF EXISTS {0} CASCADE'.format(name))
        cur.execute("""
            TRUNCATE utenti, ruoli, arruolati, produttori, dettagli_ordini,
                     movimenti, tipologie_movimenti, ricariche_esterne
            RESTART IDENTITY CASCADE
        """)
    conn.close()
    yield


@pytest.fixture
def app():
    os.environ['DELEK_LOCAL_DB'] = TEST_DB
    os.environ.setdefault('SECRET_KEY', 'test-secret-key')
    flask_app = create_app(local=True)
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def get_csrf_token(client, url):
    """Recupera un token CSRF valido dalla pagina data, cosi i test POST
    esercitano il percorso reale (CSRFProtect attivo, come in produzione)
    invece di disabilitare la protezione durante i test."""
    resp = client.get(url)
    match = re.search(r'name="csrf_token" value="([^"]+)"', resp.data.decode('utf8'))
    assert match, 'csrf_token non trovato in {0}'.format(url)
    return match.group(1)


@pytest.fixture
def moderatore():
    """Crea un utente con ruolo 'moderatore' direttamente via SQL (più
    veloce e isolato dal passare per le route di registrazione/permessi)"""
    conn = _connect(TEST_DB)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO utenti (username, password, email, attivo)"
            " VALUES (%s, %s, %s, true) RETURNING id",
            ('modtest', generate_password_hash('pwtest'), 'mod@test.it'),
        )
        id_utente = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO ruoli (nome, descrizione) VALUES ('moderatore', '')"
            " RETURNING id"
        )
        id_ruolo = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO arruolati (id_ruolo, id_utente) VALUES (%s, %s)",
            (id_ruolo, id_utente),
        )
    conn.close()
    return {'username': 'modtest', 'password': 'pwtest', 'id': id_utente}


@pytest.fixture
def login_moderatore(client, moderatore):
    """Autentica il client come moderatore (sessione via cookie), tramite
    un vero POST /auth/login con token CSRF valido."""
    token = get_csrf_token(client, '/auth/login')
    resp = client.post(
        '/auth/login',
        data={
            'username': moderatore['username'],
            'password': moderatore['password'],
            'csrf_token': token,
        },
    )
    assert resp.status_code == 302, resp.data
    return client


@pytest.fixture
def produttore_con_listino():
    """Crea un produttore con un listino_N non vuoto (precondizione di
    ordini.create) e le tabelle dinamiche listino_N/ordine_in_corso_N,
    con lo stesso DDL usato da produttori.controller.create()."""
    conn = _connect(TEST_DB)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO produttori (nome, mask_mesi_consegna)"
            " VALUES (%s, B'000000000000') RETURNING id",
            ('Produttore Test',),
        )
        id_produttore = cur.fetchone()[0]
        cur.execute("""
            CREATE TABLE listino_{0} (
                id SERIAL PRIMARY KEY,
                categoria TEXT DEFAULT '',
                disponibile BOOLEAN DEFAULT TRUE,
                descrizione_prodotto TEXT NOT NULL,
                dettaglio_qta TEXT,
                prezzo NUMERIC(7, 2) NOT NULL,
                n_min_colli INTEGER DEFAULT 1,
                n_max_colli INTEGER DEFAULT 0,
                colli_disponibili INTEGER DEFAULT 0,
                nota TEXT)
        """.format(id_produttore))
        cur.execute("""
            CREATE TABLE ordine_in_corso_{0} (
                id SERIAL PRIMARY KEY,
                id_utente INTEGER NOT NULL,
                id_prodotto INTEGER NOT NULL,
                colli_richiesti SMALLINT NOT NULL,
                specifica TEXT,
                effettuato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_utente) REFERENCES utenti (id),
                FOREIGN KEY (id_prodotto) REFERENCES listino_{0} (id))
        """.format(id_produttore))
        cur.execute(
            "INSERT INTO listino_{0}"
            " (descrizione_prodotto, prezzo) VALUES (%s, %s)".format(id_produttore),
            ('Prodotto Test', 9.99),
        )
    conn.close()
    return id_produttore
