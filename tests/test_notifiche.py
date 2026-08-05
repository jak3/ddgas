"""Test per le iscrizioni ai promemoria di scadenza ordine e per l'invio."""

from datetime import timedelta
from unittest.mock import patch

import psycopg2
from werkzeug.security import generate_password_hash

from delek.controller import notifiche
from delek.controller.tempo import adesso
from tests.conftest import DB_HOST, TEST_DB, get_csrf_token


def _connect():
    conn = psycopg2.connect(dbname=TEST_DB, host=DB_HOST)
    conn.autocommit = True
    return conn


def _crea_utente(cur, username):
    cur.execute(
        "INSERT INTO utenti (username, password, email, attivo)"
        " VALUES (%s, %s, %s, true) RETURNING id",
        (username, generate_password_hash('pw'), '{0}@test.it'.format(username)),
    )
    return cur.fetchone()[0]


def _crea_dettaglio_ordine(cur, id_produttore, scadenza):
    cur.execute(
        "INSERT INTO dettagli_ordini (id_produttore, scadenza, consegna)"
        " VALUES (%s, %s, %s) RETURNING id",
        (id_produttore, scadenza, scadenza + timedelta(days=2)),
    )
    return cur.fetchone()[0]


def test_produttore_iscrizione_post_only_e_idempotente(
    login_moderatore, produttore_con_listino
):
    client = login_moderatore

    resp = client.get(
        '/notifiche/produttore/{0}/iscriviti'.format(produttore_con_listino)
    )
    assert resp.status_code == 405, resp.data

    token = get_csrf_token(client, '/produttori/create')
    for _ in range(2):
        resp = client.post(
            '/notifiche/produttore/{0}/iscriviti'.format(produttore_con_listino),
            data={'csrf_token': token},
        )
        assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT COUNT(*) FROM notifiche_produttore WHERE id_produttore = %s',
            (produttore_con_listino,),
        )
        assert cur.fetchone()[0] == 1
    conn.close()

    for _ in range(2):
        resp = client.post(
            '/notifiche/produttore/{0}/disiscriviti'.format(produttore_con_listino),
            data={'csrf_token': token},
        )
        assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT COUNT(*) FROM notifiche_produttore WHERE id_produttore = %s',
            (produttore_con_listino,),
        )
        assert cur.fetchone()[0] == 0
    conn.close()


def test_ordine_iscrizione_post_only_e_idempotente(
    login_moderatore, produttore_con_listino, moderatore
):
    conn = _connect()
    with conn.cursor() as cur:
        id_dettaglio = _crea_dettaglio_ordine(
            cur, produttore_con_listino, adesso() + timedelta(hours=12)
        )
        # @sollecito su ordini.list_ordini() reindirizza a /auth/info se
        # mancano nome/cognome/cf: la fixture moderatore non li imposta.
        cur.execute(
            "UPDATE utenti SET nome = 'Test', cognome = 'Test', cf = 'TSTTST00A00A000A'"
            " WHERE id = %s",
            (moderatore['id'],),
        )
    conn.close()

    client = login_moderatore

    # ordini/list.html renderizza i bottoni di iscrizione nel loop su
    # ordini_scadenza: verifica che il template non rompa con un ordine
    # attivo davvero presente (a differenza degli altri test in questo
    # file, dove ordini_scadenza resta vuoto).
    resp = client.get('/ordini/')
    assert resp.status_code == 200, resp.data
    assert 'notifiche/ordine/{0}/iscriviti'.format(id_dettaglio).encode() in resp.data

    resp = client.get('/notifiche/ordine/{0}/iscriviti'.format(id_dettaglio))
    assert resp.status_code == 405, resp.data

    token = get_csrf_token(client, '/produttori/create')
    for _ in range(2):
        resp = client.post(
            '/notifiche/ordine/{0}/iscriviti'.format(id_dettaglio),
            data={'csrf_token': token},
        )
        assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT COUNT(*) FROM notifiche_ordine WHERE id_dettaglio_ordine = %s',
            (id_dettaglio,),
        )
        assert cur.fetchone()[0] == 1
    conn.close()

    resp = client.get('/ordini/')
    assert 'notifiche/ordine/{0}/disiscriviti'.format(id_dettaglio).encode() in resp.data

    for _ in range(2):
        resp = client.post(
            '/notifiche/ordine/{0}/disiscriviti'.format(id_dettaglio),
            data={'csrf_token': token},
        )
        assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT COUNT(*) FROM notifiche_ordine WHERE id_dettaglio_ordine = %s',
            (id_dettaglio,),
        )
        assert cur.fetchone()[0] == 0
    conn.close()


@patch('delek.controller.notifiche.SendGridAPIClient')
def test_esegui_promemoria_ordini_destinatari_e_idempotenza(
    mock_sendgrid_client, app, produttore_con_listino
):
    """Referenti (sempre) + iscritti permanenti + iscritti one-off ricevono
    il promemoria, un utente non iscritto no; un secondo run non re-invia;
    un ordine fuori dalla finestra delle 24h non viene processato."""
    conn = _connect()
    with conn.cursor() as cur:
        id_referente = _crea_utente(cur, 'referente1')
        id_permanente = _crea_utente(cur, 'permanente1')
        id_one_off = _crea_utente(cur, 'oneoff1')
        _crea_utente(cur, 'controllo1')  # non iscritto, non deve ricevere nulla

        id_dettaglio_vicino = _crea_dettaglio_ordine(
            cur, produttore_con_listino, adesso() + timedelta(hours=12)
        )
        cur.execute(
            'INSERT INTO referenze (id_produttore, id_utente) VALUES (%s, %s)',
            (produttore_con_listino, id_referente),
        )
        cur.execute(
            'INSERT INTO notifiche_produttore (id_utente, id_produttore)'
            ' VALUES (%s, %s)',
            (id_permanente, produttore_con_listino),
        )
        cur.execute(
            'INSERT INTO notifiche_ordine (id_utente, id_dettaglio_ordine)'
            ' VALUES (%s, %s)',
            (id_one_off, id_dettaglio_vicino),
        )

        # Un secondo produttore/ordine fuori dalla finestra delle 24h: non
        # deve generare nessun invio.
        cur.execute(
            "INSERT INTO produttori (nome, mask_mesi_consegna)"
            " VALUES ('Produttore Lontano', B'000000000000') RETURNING id"
        )
        id_produttore_lontano = cur.fetchone()[0]
        _crea_dettaglio_ordine(
            cur, id_produttore_lontano, adesso() + timedelta(days=3)
        )
    conn.close()

    mock_send = mock_sendgrid_client.return_value.send

    with app.app_context():
        riepilogo = notifiche.esegui_promemoria_ordini()

    assert 'ordini processati' in riepilogo

    inviati_a = {
        call.args[0].get()['personalizations'][0]['to'][0]['email']
        for call in mock_send.call_args_list
    }
    assert inviati_a == {'referente1@test.it', 'permanente1@test.it', 'oneoff1@test.it'}

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT promemoria_inviato FROM dettagli_ordini WHERE id = %s',
            (id_dettaglio_vicino,),
        )
        assert cur.fetchone()[0] is True

        cur.execute(
            'SELECT promemoria_inviato FROM dettagli_ordini WHERE id_produttore = %s',
            (id_produttore_lontano,),
        )
        assert cur.fetchone()[0] is False
    conn.close()

    mock_send.reset_mock()
    with app.app_context():
        notifiche.esegui_promemoria_ordini()
    assert mock_send.call_count == 0, 'un ordine già processato non va rinotificato'


def test_modifica_scadenza_resetta_promemoria_inviato(
    login_moderatore, produttore_con_listino
):
    conn = _connect()
    with conn.cursor() as cur:
        id_dettaglio = _crea_dettaglio_ordine(
            cur, produttore_con_listino, adesso() + timedelta(hours=12)
        )
        cur.execute(
            'UPDATE dettagli_ordini SET promemoria_inviato = TRUE WHERE id = %s',
            (id_dettaglio,),
        )
    conn.close()

    client = login_moderatore
    token = get_csrf_token(
        client, '/ordini/update/{0}'.format(produttore_con_listino)
    )
    nuova_scadenza = (adesso() + timedelta(days=3)).strftime('%Y-%m-%d')
    nuova_consegna = (adesso() + timedelta(days=5)).strftime('%Y-%m-%d')
    resp = client.post(
        '/ordini/update/{0}'.format(produttore_con_listino),
        data={
            'id_produttore': produttore_con_listino,
            'scadenza': nuova_scadenza,
            'consegna': nuova_consegna,
            'minimo_ordine': '',
            'nota': '',
            'csrf_token': token,
        },
    )
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT promemoria_inviato FROM dettagli_ordini WHERE id = %s',
            (id_dettaglio,),
        )
        assert cur.fetchone()[0] is False
    conn.close()
