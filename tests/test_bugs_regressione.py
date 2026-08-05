"""Regressioni per bug scoperti verificando end-to-end le modifiche di
questa sessione (vedi DEV.md/git log): tutti presenti già in produzione
prima di queste modifiche, non introdotti dai refactor che li hanno
scoperti."""

import psycopg2
from werkzeug.security import generate_password_hash

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


def test_presidi_newy_non_duplica_e_richiede_post(login_moderatore):
    """newy() chiamava INSERT due volte per ogni giorno nel loop: ogni
    click su "Genera Date Anno in Corso" duplicava tutte le righe. La
    route era anche una GET che scrive sul DB, cliccabile/crawlabile
    senza alcuna protezione CSRF (stessa classe di bug già corretta per
    movimenti.delete): ora richiede POST."""
    client = login_moderatore

    resp = client.get('/presidi/newy')
    assert resp.status_code == 405, resp.data

    token = get_csrf_token(client, '/presidi/')
    resp = client.post('/presidi/newy', data={'csrf_token': token})
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT giorno FROM presidi GROUP BY giorno HAVING COUNT(*) > 1'
        )
        assert cur.fetchall() == [], 'newy ha inserito righe duplicate'
    conn.close()


def test_presidi_unbooking_richiede_autorizzazione(app, moderatore):
    """unbooking() non controllava affatto chi stesse chiamando (solo
    login_required, nessun controllo di proprietà/ruolo): qualunque
    utente loggato poteva disdire la prenotazione di un altro
    conoscendone/indovinandone l'id (IDOR). Il template nascondeva il
    link ma non proteggeva la route."""
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO presidi (giorno, id_utente)"
            " VALUES (now() + interval '7 days', %s) RETURNING id",
            (moderatore['id'],),
        )
        id_presidio = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO utenti (username, password, email, attivo)"
            " VALUES ('altro', %s, 'altro@test.it', true) RETURNING id",
            (generate_password_hash('pwaltro'),),
        )
    conn.close()

    other_client = app.test_client()
    token = get_csrf_token(other_client, '/auth/login')
    resp = other_client.post(
        '/auth/login',
        data={'username': 'altro', 'password': 'pwaltro', 'csrf_token': token},
    )
    assert resp.status_code == 302, resp.data

    token = get_csrf_token(other_client, '/presidi/')
    resp = other_client.post(
        '/presidi/unbooking/{0}'.format(id_presidio), data={'csrf_token': token}
    )
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute('SELECT id_utente FROM presidi WHERE id = %s', (id_presidio,))
        assert cur.fetchone()[0] == moderatore['id'], (
            'un utente non autorizzato ha rimosso la prenotazione altrui'
        )
    conn.close()


def test_produttori_remove_referente_richiede_post(
    login_moderatore, produttore_con_listino
):
    """remove_referente() era una GET che cancella (DELETE FROM
    referenze), linkata come <a href> in produttori/update.html: bastava
    un click, senza CSRF. Ora richiede POST."""
    client = login_moderatore
    resp = client.get('/produttori/{0}/1/delete'.format(produttore_con_listino))
    assert resp.status_code == 405, resp.data


def test_ordini_rimuovi_singolo_ordine_richiede_post(
    login_moderatore, moderatore, produttore_con_listino
):
    """rimuovi_singolo_ordine() era una GET che cancella (DELETE FROM
    ordine_in_corso_N), linkata come <a href> in ordini/rettifica.html
    dentro il <form> principale della rettifica (non annidabile in un
    secondo <form>): risolto con l'attributo HTML5 form= verso un <form>
    nascosto esterno. La route ora richiede POST."""
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dettagli_ordini (id_produttore, scadenza, consegna)"
            " VALUES (%s, now(), now())",
            (produttore_con_listino,),
        )
        cur.execute('SELECT id FROM listino_{0} LIMIT 1'.format(produttore_con_listino))
        id_prodotto = cur.fetchone()[0]
        cur.execute(
            'INSERT INTO ordine_in_corso_{0}'
            ' (id_utente, id_prodotto, colli_richiesti) VALUES (%s, %s, 1)'.format(
                produttore_con_listino
            ),
            (moderatore['id'], id_prodotto),
        )
    conn.close()

    client = login_moderatore

    resp = client.get('/ordini/rettifica/{0}'.format(produttore_con_listino))
    assert resp.status_code == 200, resp.data
    assert b'rimuovi-ordine-' in resp.data

    resp = client.get(
        '/ordini/rettifica/{0}/rimuovi/{1}'.format(
            produttore_con_listino, moderatore['id']
        )
    )
    assert resp.status_code == 405, resp.data

    token = get_csrf_token(
        client, '/ordini/rettifica/{0}'.format(produttore_con_listino)
    )
    resp = client.post(
        '/ordini/rettifica/{0}/rimuovi/{1}'.format(
            produttore_con_listino, moderatore['id']
        ),
        data={'csrf_token': token},
    )
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT * FROM ordine_in_corso_{0} WHERE id_utente = %s'.format(
                produttore_con_listino
            ),
            (moderatore['id'],),
        )
        assert cur.fetchone() is None, "l'ordine non è stato rimosso"
    conn.close()
