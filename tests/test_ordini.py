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

from delek.controller.tempo import adesso
from tests.conftest import TEST_DB

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
