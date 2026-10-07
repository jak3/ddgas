""" Test per la classificazione degli ordini tra "Le Tue Prossime
Consegne" e "In Fase di Rettifica" nella pagina /ordini/.

Regressione per un bug segnalato da un gasista: il giorno stesso della
consegna (latte, consegnato al mattino), guardando la pagina la sera il
produttore risultava già sotto "In Fase di Rettifica" invece che "Le Tue
Prossime Consegne". Causa: create()/update() assegnano sempre le 19:00 al
campo 'consegna', a prescindere dall'orario reale della consegna, e
list_ordini() confrontava l'orario esatto (consegna < adesso()) invece
del solo giorno di calendario. """

from datetime import timedelta
from unittest.mock import patch

from delek.controller.tempo import adesso
from tests.conftest import TEST_DB, get_csrf_token

import psycopg2


def _connect():
    conn = psycopg2.connect(dbname=TEST_DB, host='127.0.0.1')
    conn.autocommit = True
    return conn


def test_consegna_oggi_resta_tra_le_prossime_consegne(
    login_moderatore, moderatore, produttore_con_listino
):
    """ Guardando la pagina la sera dello stesso giorno della consegna
    (dopo le 19:00 fissate internamente su 'consegna'), l'ordine deve
    restare sotto "Le Tue Prossime Consegne", non apparire già come "In
    Fase di Rettifica": il confronto va fatto sul giorno di calendario,
    non sull'orario esatto. """
    id_produttore = produttore_con_listino
    conn = _connect()
    with conn.cursor() as cur:
        # @sollecito su list_ordini() reindirizza a /auth/info se mancano
        # nome/cognome/cf: la fixture moderatore non li imposta.
        cur.execute(
            "UPDATE utenti SET nome = 'Test', cognome = 'Test',"
            " cf = 'TSTTST00A00A000A' WHERE id = %s", (moderatore['id'],))
        cur.execute(
            'SELECT id FROM listino_{0} LIMIT 1'.format(id_produttore))
        id_prodotto = cur.fetchone()[0]
        # scadenza passata, consegna oggi ma a un orario già passato
        # rispetto ad "adesso" (simula di guardare la pagina a sera)
        cur.execute(
            "INSERT INTO dettagli_ordini (id_produttore, scadenza, consegna)"
            " VALUES (%s, %s, %s)",
            (id_produttore, adesso() - timedelta(hours=1),
             adesso() - timedelta(minutes=1)),
        )
        cur.execute(
            'INSERT INTO ordine_in_corso_{0}'
            ' (id_utente, id_prodotto, colli_richiesti) VALUES (%s, %s, 1)'
            .format(id_produttore),
            (moderatore['id'], id_prodotto),
        )
    conn.close()

    resp = login_moderatore.get('/ordini/')
    assert resp.status_code == 200, resp.data
    assert '/ordini/update/{0}'.format(id_produttore).encode() in resp.data, (
        "l'ordine dovrebbe comparire tra 'Le Tue Prossime Consegne'"
        " (bottone Modifica) lo stesso giorno della consegna")
    assert ('/ordini/rettifica/{0}'.format(id_produttore).encode()
            not in resp.data), (
        "l'ordine non dovrebbe ancora comparire in 'In Fase di Rettifica'"
        " lo stesso giorno della consegna")


def test_consegna_ieri_passa_in_fase_di_rettifica(
    login_moderatore, moderatore, produttore_con_listino
):
    """ Non-regressione: dal giorno successivo alla consegna, l'ordine
    deve comunque passare in "In Fase di Rettifica". """
    id_produttore = produttore_con_listino
    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE utenti SET nome = 'Test', cognome = 'Test',"
            " cf = 'TSTTST00A00A000A' WHERE id = %s", (moderatore['id'],))
        cur.execute(
            'SELECT id FROM listino_{0} LIMIT 1'.format(id_produttore))
        id_prodotto = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO dettagli_ordini (id_produttore, scadenza, consegna)"
            " VALUES (%s, %s, %s)",
            (id_produttore, adesso() - timedelta(days=2),
             adesso() - timedelta(days=1)),
        )
        cur.execute(
            'INSERT INTO ordine_in_corso_{0}'
            ' (id_utente, id_prodotto, colli_richiesti) VALUES (%s, %s, 1)'
            .format(id_produttore),
            (moderatore['id'], id_prodotto),
        )
    conn.close()

    resp = login_moderatore.get('/ordini/')
    assert resp.status_code == 200, resp.data
    assert ('/ordini/rettifica/{0}'.format(id_produttore).encode()
            in resp.data), (
        "l'ordine dovrebbe comparire in 'In Fase di Rettifica' il giorno"
        " dopo la consegna")


def _post_create_ordine(client, id_produttore, **extra):
    token = get_csrf_token(client, '/ordini/create')
    data = {
        'id_produttore': id_produttore,
        'scadenza': (adesso() + timedelta(days=3)).strftime('%Y-%m-%d'),
        'consegna': (adesso() + timedelta(days=7)).strftime('%Y-%m-%d'),
        'minimo_ordine': '',
        'csrf_token': token,
    }
    data.update(extra)
    return client.post('/ordini/create', data=data)


@patch('delek.controller.notifiche.SendGridAPIClient')
def test_apertura_ordine_invia_una_email_alla_mailing_list(
    mock_sendgrid_client, app, login_moderatore, produttore_con_listino
):
    """ Aprire un nuovo ordine deve inviare UNA sola email all'indirizzo
    impostato in config/associazione.yaml (regole.
    mailing_list_apertura_ordini), non una per ogni gasista iscritto. """
    app.config['ASSOCIAZIONE']['regole']['mailing_list_apertura_ordini'] = (
        'dai-gas@googlegroups.com')
    mock_send = mock_sendgrid_client.return_value.send

    resp = _post_create_ordine(login_moderatore, produttore_con_listino,
                               nota='Portare sacchetti')
    assert resp.status_code == 302, resp.data
    assert mock_send.call_count == 1

    msg = mock_send.call_args.args[0].get()
    assert (msg['personalizations'][0]['to'][0]['email']
           == 'dai-gas@googlegroups.com')
    assert 'Produttore Test' in msg['subject']
    corpo = msg['content'][0]['value']
    assert 'Produttore Test' in corpo
    assert 'Portare sacchetti' in corpo
    assert '/ordini/effettua/{0}'.format(produttore_con_listino) in corpo


@patch('delek.controller.notifiche.SendGridAPIClient')
def test_apertura_ordine_creato_anche_se_invio_email_fallisce(
    mock_sendgrid_client, app, login_moderatore, produttore_con_listino
):
    """ Un fallimento dell'invio della notifica non deve mai impedire la
    creazione dell'ordine, già avvenuta nello stesso INSERT. """
    app.config['ASSOCIAZIONE']['regole']['mailing_list_apertura_ordini'] = (
        'dai-gas@googlegroups.com')
    mock_sendgrid_client.return_value.send.side_effect = Exception('boom')

    resp = _post_create_ordine(login_moderatore, produttore_con_listino)
    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT id FROM dettagli_ordini WHERE id_produttore = %s',
            (produttore_con_listino,))
        assert cur.fetchone() is not None, (
            "l'ordine deve essere creato anche se l'invio della notifica"
            " fallisce")
    conn.close()


@patch('delek.controller.notifiche.SendGridAPIClient')
def test_apertura_ordine_senza_mailing_list_configurata_non_invia(
    mock_sendgrid_client, app, login_moderatore, produttore_con_listino
):
    """ Senza regole.mailing_list_apertura_ordini configurata (default
    per una nuova installazione), la notifica viene saltata
    silenziosamente e l'ordine si crea comunque. """
    app.config['ASSOCIAZIONE']['regole']['mailing_list_apertura_ordini'] = None

    resp = _post_create_ordine(login_moderatore, produttore_con_listino)
    assert resp.status_code == 302, resp.data
    assert mock_sendgrid_client.return_value.send.call_count == 0

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT id FROM dettagli_ordini WHERE id_produttore = %s',
            (produttore_con_listino,))
        assert cur.fetchone() is not None
    conn.close()
