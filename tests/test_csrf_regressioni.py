"""Regressioni per la classe di bug scoperta portando il CSRF da ddgas:
da quando ogni form POST include un campo csrf_token, le route che
costruiscono la query SQL dinamicamente a partire dai nomi dei campi del
form (senza whitelist) provano a scrivere su una colonna 'csrf_token'
inesistente e falliscono con un 500. Ogni test qui sotto invia un vero
csrf_token (CSRF resta attivo, non viene disabilitato) proprio per
riprodurre le condizioni reali."""

from datetime import timedelta

import psycopg2

from delek.controller.tempo import adesso
from tests.conftest import DB_HOST, TEST_DB, get_csrf_token


def _connect():
    conn = psycopg2.connect(dbname=TEST_DB, host=DB_HOST)
    conn.autocommit = True
    return conn


def test_ordini_create_non_fallisce_con_csrf_token(
    login_moderatore, produttore_con_listino
):
    client = login_moderatore
    token = get_csrf_token(client, '/ordini/create')

    resp = client.post(
        '/ordini/create',
        data={
            'id_produttore': produttore_con_listino,
            # Relative ad adesso(), non date fisse: 'create' rifiuta
            # scadenza/consegna nel passato, e una data fissa scade.
            'scadenza': (adesso() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'consegna': (adesso() + timedelta(days=10)).strftime('%Y-%m-%d'),
            'minimo_ordine': '',
            'nota': '',
            'csrf_token': token,
        },
    )

    assert resp.status_code == 302, resp.data
    assert resp.headers['Location'].endswith('/ordini/')

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT id_produttore FROM dettagli_ordini WHERE id_produttore = %s',
            (produttore_con_listino,),
        )
        assert (
            cur.fetchone() is not None
        ), "l'ordine non risulta creato in dettagli_ordini"
    conn.close()


def test_ordini_update_non_fallisce_con_csrf_token(
    login_moderatore, produttore_con_listino
):
    client = login_moderatore

    # Precondizione: un ordine già aperto da modificare.
    token = get_csrf_token(client, '/ordini/create')
    resp_create = client.post(
        '/ordini/create',
        data={
            'id_produttore': produttore_con_listino,
            'scadenza': (adesso() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'consegna': (adesso() + timedelta(days=10)).strftime('%Y-%m-%d'),
            'minimo_ordine': '',
            'nota': '',
            'csrf_token': token,
        },
    )
    assert resp_create.status_code == 302, resp_create.data

    token = get_csrf_token(client, '/ordini/update/{0}'.format(produttore_con_listino))
    resp = client.post(
        '/ordini/update/{0}'.format(produttore_con_listino),
        data={
            'id_produttore': produttore_con_listino,
            'scadenza': (adesso() + timedelta(days=6)).strftime('%Y-%m-%d'),
            'consegna': (adesso() + timedelta(days=11)).strftime('%Y-%m-%d'),
            'minimo_ordine': '',
            'nota': 'Nota aggiornata',
            'csrf_token': token,
        },
    )

    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT nota FROM dettagli_ordini WHERE id_produttore = %s',
            (produttore_con_listino,),
        )
        assert cur.fetchone()[0] == 'Nota aggiornata'
    conn.close()


def test_listini_create_non_fallisce_con_csrf_token(
    login_moderatore, produttore_con_listino
):
    client = login_moderatore
    url = '/listini/{0}/create'.format(produttore_con_listino)
    token = get_csrf_token(client, url)

    resp = client.post(
        url,
        data={
            'descrizione_prodotto': 'Nuovo Prodotto Test',
            'dettaglio_qta': '',
            'disponibile': '1',
            'prezzo': '4.50',
            'n_min_colli': '1',
            'n_max_colli': '0',
            'colli_disponibili': '0',
            'categoria': '',
            'nota': '',
            'csrf_token': token,
        },
    )

    assert resp.status_code == 302, resp.data

    conn = _connect()
    with conn.cursor() as cur:
        cur.execute(
            'SELECT descrizione_prodotto FROM listino_{0}'
            " WHERE descrizione_prodotto = 'Nuovo Prodotto Test'".format(
                produttore_con_listino
            )
        )
        assert cur.fetchone() is not None
    conn.close()
