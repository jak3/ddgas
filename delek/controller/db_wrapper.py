''' Funzioni utili per query al DB utilizzati da diversi controller '''

from flask import g
from delek.controller.db import get_db
from delek.controller.movimenti import get_totale_utente


def get_spesa_totale_utenti(id_produttore):
    """ Ritorna la spesa totale dell'ordine in corso verso id_produttore per
        singolo utente """
    get_db().execute(
        """
        SELECT id_utente, SUM(colli_richiesti * prezzo) as totale
        FROM ordine_in_corso_{0} INNER JOIN listino_{0}
                ON listino_{0}.id = id_prodotto
        GROUP BY id_utente
        """.format(id_produttore)
    )

    return dict(get_db().fetchall())


def get_spesa_totale_in_ordinazione():
    """ Ritorna il totale per gli ordini effettuati ancora però da confermare.
        Utilizzato per dare all'utente un idea del totale che avrebbe se tutti
        gli ordini che ha effettuato andranno a buon fine """
    dbi = get_db()
    dbi.execute('SELECT id_produttore FROM dettagli_ordini')
    id_produttori_in_lavorazione = [dettaglio['id_produttore']
                                    for dettaglio in dbi.fetchall()]
    totale = 0
    for id_produttore in id_produttori_in_lavorazione:
        spesa_utenti = get_spesa_totale_utenti(id_produttore)
        if g.user['id'] in spesa_utenti.keys():
            totale += float(spesa_utenti[g.user['id']])
    return totale


def get_totale_utente_temporaneo():
    """ Ritorna il totale per l'utente corrente, includendo i totali degli
        ordini che devono ancora essere confermati (rettificati) """
    return (float(get_totale_utente(g.user['id'])) -
            get_spesa_totale_in_ordinazione())
