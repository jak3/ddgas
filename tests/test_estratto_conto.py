"""Test per l'import dell'estratto conto e le ricariche via bonifico."""

import io

import psycopg2
from werkzeug.security import generate_password_hash

from tests.conftest import DB_HOST, TEST_DB, get_csrf_token


def _connect():
    conn = psycopg2.connect(dbname=TEST_DB, host=DB_HOST)
    conn.autocommit = True
    return conn


def _crea_utente(cur, username, attivo=True):
    cur.execute(
        "INSERT INTO utenti (username, password, email, attivo)"
        " VALUES (%s, %s, %s, %s) RETURNING id",
        (username, generate_password_hash('pw'), '{0}@test.it'.format(username), attivo),
    )
    return cur.fetchone()[0]


def _imposta_configurazione(cur):
    cur.execute("""
        INSERT INTO configurazione_estratto_conto
            (id, colonna_data, colonna_causale, colonna_importo,
             formato_data, separatore_csv, decimale_virgola, encoding)
        VALUES (1, 'Data', 'Causale', 'Importo', '%d/%m/%Y', ';', true, 'utf-8')
    """)


def _csv(righe):
    """righe: lista di (data, causale, importo) come stringhe già nel
    formato/separatore atteso dalla configurazione di test."""
    testo = 'Data;Causale;Importo\n' + '\n'.join(';'.join(r) for r in righe)
    return io.BytesIO(testo.encode('utf-8'))


def _upload(client, righe):
    token = get_csrf_token(client, '/estratto-conto/importa')
    return client.post(
        '/estratto-conto/importa',
        data={
            'estratto': (_csv(righe), 'estratto.csv'),
            'csrf_token': token,
        },
        content_type='multipart/form-data',
    )


def test_dichiara_raggiungibile_senza_stripe_configurato(login_moderatore, moderatore):
    """pagamenti_bp non è registrato senza STRIPE_SECRET_KEY (mai impostata
    nei test): estratto_conto deve restare raggiungibile comunque, essendo
    un blueprint sempre registrato."""
    client = login_moderatore
    token = get_csrf_token(client, '/estratto-conto/dichiara')
    resp = client.post(
        '/estratto-conto/dichiara', data={'importo': '30', 'csrf_token': token}
    )
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT stato, importo FROM ricariche_esterne"
            " WHERE provider = 'bonifico' AND id_utente = %s",
            (moderatore['id'],),
        )
        row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 'creato'
    assert float(row[1]) == 30.0


def test_configurazione_upsert(login_moderatore):
    client = login_moderatore
    token = get_csrf_token(client, '/estratto-conto/configurazione')
    resp = client.post(
        '/estratto-conto/configurazione',
        data={
            'colonna_data': 'Data valuta',
            'colonna_causale': 'Causale',
            'colonna_importo': 'Importo',
            'formato_data': '%d/%m/%Y',
            'separatore_csv': ';',
            'encoding': 'utf-8',
            'decimale_virgola': '1',
            'csrf_token': token,
        },
    )
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT colonna_data, decimale_virgola'
            ' FROM configurazione_estratto_conto WHERE id = 1'
        )
        row = cur.fetchone()
    conn.close()
    assert row == ('Data valuta', True)


def test_configurazione_richiede_moderatore(client):
    conn = _connect()
    with conn.cursor() as cur:
        _crea_utente(cur, 'gasista1')
    conn.close()

    token = get_csrf_token(client, '/auth/login')
    resp = client.post(
        '/auth/login',
        data={'username': 'gasista1', 'password': 'pw', 'csrf_token': token},
    )
    assert resp.status_code == 302, resp.data

    resp = client.get('/estratto-conto/configurazione')
    assert resp.status_code == 403


def test_importa_senza_configurazione_redirige(login_moderatore):
    resp = login_moderatore.get('/estratto-conto/importa')
    assert resp.status_code == 302
    assert '/estratto-conto/configurazione' in resp.headers['Location']


def test_importa_matching_e_regressioni(login_moderatore, moderatore):
    """Scenario completo di import: dichiarazione+importo, causale da sola,
    riga ambigua, collisione RIC-<id> (regressione), utente disattivato
    (regressione), importo negativo scartato in parsing."""
    client = login_moderatore
    # Chi dichiara è chi ha fatto login: la fixture 'moderatore'.
    id_dichiarante = moderatore['id']

    conn = _connect()
    with conn.cursor() as cur:
        _imposta_configurazione(cur)
        # insert_movimento() usa tipologia=1 ('versamento'): _clean_db
        # tronca tipologie_movimenti a ogni test, i dati di bootstrap.sql
        # non sono applicati al DB di test, va seminato qui.
        cur.execute("INSERT INTO tipologie_movimenti (id, nome) VALUES (1, 'versamento')")
        id_causale = _crea_utente(cur, 'causalematch')
        id_ambiguo1 = _crea_utente(cur, 'ambiguo1')
        id_ambiguo2 = _crea_utente(cur, 'ambiguo2')
        id_ric = _crea_utente(cur, 'riccode')
        _crea_utente(cur, 'disattivato', attivo=False)
    conn.close()

    # Dichiarazione preventiva: 42.00€, nessun aiuto dalla causale.
    token = get_csrf_token(client, '/estratto-conto/dichiara')
    resp = client.post(
        '/estratto-conto/dichiara',
        data={'importo': '42.00', 'csrf_token': token},
    )
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        # Due dichiarazioni pendenti allo stesso importo: ambigua senza
        # aiuto dalla causale.
        cur.execute(
            "INSERT INTO ricariche_esterne (provider, provider_ref, id_utente, importo)"
            " VALUES ('bonifico', 'test-ambiguo-1', %s, 15.00)",
            (id_ambiguo1,),
        )
        cur.execute(
            "INSERT INTO ricariche_esterne (provider, provider_ref, id_utente, importo)"
            " VALUES ('bonifico', 'test-ambiguo-2', %s, 15.00)",
            (id_ambiguo2,),
        )
    conn.close()

    righe = [
        ('24/08/2026', 'versamento gas', '42,00'),  # dichiarazione+importo
        ('24/08/2026', 'bonifico causalematch mensile', '18,50'),  # solo causale
        ('24/08/2026', 'bonifico generico', '15,00'),  # ambigua
        # 'ric-<id>9' non è delimitato da confini di parola: non deve
        # combaciare con RIC-<id> (regressione sulla collisione trovata in
        # review, es. RIC-1 dentro RIC-12).
        ('24/08/2026', 'RIC-{0}9 pagamento'.format(id_ric), '77,00'),
        # utente disattivato: il suo username in causale non deve bastare
        # a farlo accreditare (get_utenti va filtrato su attivo).
        ('24/08/2026', 'versamento disattivato', '33,00'),
        ('24/08/2026', 'spesa fornitore', '-20,00'),  # uscita, va ignorata
    ]
    resp = _upload(client, righe)
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM righe_estratto_conto')
        assert cur.fetchone()[0] == 5  # l'uscita non genera nessuna riga

        cur.execute(
            "SELECT stato, id_utente FROM righe_estratto_conto WHERE importo = 42.00"
        )
        assert cur.fetchone() == ('accreditato', id_dichiarante)

        cur.execute(
            "SELECT stato, id_utente FROM righe_estratto_conto WHERE importo = 18.50"
        )
        assert cur.fetchone() == ('accreditato', id_causale)

        cur.execute(
            "SELECT stato, id_utente FROM righe_estratto_conto WHERE importo = 15.00"
        )
        assert cur.fetchone() == ('da_verificare', None)

        cur.execute(
            "SELECT stato, id_utente FROM righe_estratto_conto WHERE importo = 77.00"
        )
        assert cur.fetchone() == ('da_verificare', None)

        cur.execute(
            "SELECT stato, id_utente FROM righe_estratto_conto WHERE importo = 33.00"
        )
        assert cur.fetchone() == ('da_verificare', None)

        cur.execute(
            'SELECT COUNT(*) FROM movimenti WHERE per_id_utente IN (%s, %s)',
            (id_dichiarante, id_causale),
        )
        n_movimenti_dopo_primo_import = cur.fetchone()[0]
        assert n_movimenti_dopo_primo_import == 2
    conn.close()

    # Ri-caricamento dello stesso file: nessuna riga duplicata, nessun
    # doppio accredito.
    resp = _upload(client, righe)
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM righe_estratto_conto')
        assert cur.fetchone()[0] == 5
        cur.execute(
            'SELECT COUNT(*) FROM movimenti WHERE per_id_utente IN (%s, %s)',
            (id_dichiarante, id_causale),
        )
        assert cur.fetchone()[0] == n_movimenti_dopo_primo_import

        cur.execute(
            "SELECT id FROM righe_estratto_conto WHERE importo = 15.00"
        )
        id_riga_ambigua = cur.fetchone()[0]
        cur.execute(
            "SELECT id FROM righe_estratto_conto WHERE importo = 33.00"
        )
        id_riga_scarto = cur.fetchone()[0]
    conn.close()

    # Risoluzione manuale della riga ambigua: doppio submit non deve
    # accreditare due volte (provider_ref deterministico su id_riga).
    token = get_csrf_token(client, '/estratto-conto/coda')
    for _ in range(2):
        resp = client.post(
            '/estratto-conto/risolvi/{0}'.format(id_riga_ambigua),
            data={'id_utente': id_ambiguo1, 'csrf_token': token},
        )
        assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT stato, id_utente FROM righe_estratto_conto WHERE id = %s",
            (id_riga_ambigua,),
        )
        assert cur.fetchone() == ('accreditato', id_ambiguo1)
        cur.execute(
            'SELECT COUNT(*) FROM movimenti WHERE per_id_utente = %s', (id_ambiguo1,)
        )
        assert cur.fetchone()[0] == 1

        # scarta: la riga non è una ricarica, nessun accredito.
    conn.close()

    resp = client.post(
        '/estratto-conto/scarta/{0}'.format(id_riga_scarto),
        data={'csrf_token': token},
    )
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT stato, id_utente, id_movimento FROM righe_estratto_conto"
            " WHERE id = %s",
            (id_riga_scarto,),
        )
        assert cur.fetchone() == ('scartato', None, None)
    conn.close()
