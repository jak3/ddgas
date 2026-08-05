"""Regressioni per bug scoperti verificando end-to-end le modifiche di
questa sessione (vedi DEV.md/git log): tutti presenti già in produzione
prima di queste modifiche, non introdotti dai refactor che li hanno
scoperti."""

import psycopg2

from tests.conftest import DB_HOST, TEST_DB, get_csrf_token


def _connect():
    conn = psycopg2.connect(dbname=TEST_DB, host=DB_HOST)
    conn.autocommit = True
    return conn


def test_aggiorna_profilo_senza_cambiare_password(login_moderatore, moderatore):
    """check_inputs_utente() richiedeva sempre una password non vuota, ma
    _update_user() la rimuove apposta dagli inputs quando l'utente non
    vuole cambiarla: nessuno riusciva ad aggiornare telefono/email/nome
    senza reinserire anche la password."""
    client = login_moderatore
    token = get_csrf_token(client, '/auth/info')

    resp = client.post(
        '/auth/info',
        data={
            'username': moderatore['username'],
            'email': 'mod@test.it',
            'telefono': '3331234567',
            'password': '',
            'csrf_token': token,
        },
    )

    assert resp.status_code == 200, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute('SELECT telefono FROM utenti WHERE id = %s', (moderatore['id'],))
        assert cur.fetchone()[0] == '3331234567'
    conn.close()


def test_crea_produttore(login_moderatore):
    """build_mask_fix_inputs() impostava 'attivo' a un booleano Python
    (True/False) invece che alla stringa '0'/'1' richiesta dal validator
    (CeAttivo, regex ZERO_OR_ONE): ogni tentativo di creare un produttore
    falliva sempre con 'Attivo non conforme'."""
    client = login_moderatore
    token = get_csrf_token(client, '/produttori/create')

    resp = client.post(
        '/produttori/create',
        data={
            'nome': 'Produttore Nuovo',
            'email': '',
            'telefono': '',
            'website': '',
            'prodotto_principale': 'Verdura',
            'descrizione': '',
            'id_utente': 'None',
            'csrf_token': token,
        },
    )

    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("SELECT attivo FROM produttori WHERE nome = 'Produttore Nuovo'")
        assert cur.fetchone() is not None, 'il produttore non risulta creato'
    conn.close()


def test_filtro_date_movimenti(login_moderatore):
    """Gli <input type="date"> di Dal/Al non avevano l'attributo name
    (solo id): il filtro per intervallo di date non veniva mai incluso
    nel POST, quindi non ha mai filtrato nulla."""
    client = login_moderatore
    token = get_csrf_token(client, '/movimenti/list/all')

    resp = client.post(
        '/movimenti/list/all',
        data={'da_data': '2020-01-01', 'a_data': '2020-01-02', 'csrf_token': token},
    )

    assert resp.status_code == 200, resp.data
    assert b'value="2020-01-01"' in resp.data
    assert b'value="2020-01-02"' in resp.data


def test_ruoli_create_e_update_hanno_un_template(login_moderatore):
    """ruoli.create()/update() esistevano già con la logica POST completa,
    ma render_template() puntava a 'ruoli/create.html'/'update.html', mai
    creati: qualunque GET su quelle route dava TemplateNotFound (500), e
    list.html non le linkava comunque da nessuna parte."""
    client = login_moderatore

    token = get_csrf_token(client, '/ruoli/create')
    resp = client.post(
        '/ruoli/create',
        data={'nome': 'TestRuolo', 'descrizione': 'desc test', 'csrf_token': token},
    )
    assert resp.status_code == 302, resp.data

    resp = client.get('/ruoli/')
    assert b'TestRuolo' in resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM ruoli WHERE nome = 'TestRuolo'")
        idr = cur.fetchone()[0]
    conn.close()

    token = get_csrf_token(client, '/ruoli/{0}/update'.format(idr))
    resp = client.post(
        '/ruoli/{0}/update'.format(idr),
        data={'nome': 'TestRuoloMod', 'descrizione': 'desc mod', 'csrf_token': token},
    )
    assert resp.status_code == 302, resp.data

    resp = client.get('/ruoli/')
    assert b'TestRuoloMod' in resp.data
