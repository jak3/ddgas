""" Support functions to controller/ordini """
import json
from datetime import datetime
from functools import wraps

from flask import (current_app, flash, g, redirect, url_for)

from delek.controller.auth import get_utente_by_id

from delek.controller.db import get_db
from delek.controller.db_wrapper import (get_spesa_totale_utenti,
                                         get_totale_utente_temporaneo)

from delek.controller.listini import get_prodotti
from delek.controller.presidi import get_presidi


def get_ordini_in_corso(id_produttore):
    """ Ritorna le righe corrispondenti alla tabella con gli ordini in corso
    per il produttore id_produttore """

    get_db().execute("""
        SELECT {column_names} FROM ordine_in_corso_{idp}
        """.format(column_names=', '.join(
                   ['id_utente', 'id_prodotto', 'colli_richiesti',
                    'specifica']), idp=id_produttore)
    )

    return get_db().fetchall()


def get_prodotti_ordinati_da_tutti(id_produttore, id_utente=None):
    """ Ritorna tutti i prodotti ordinati da tutti i gasisti """

    ordini = get_ordini_in_corso(id_produttore)

    # { 1: {'colli_richiesti': 2, 'specifica': None},
    #   5: {'colli_richiesti': 1, 'specifica': None} }
    def filtroif(x, y): return x == y if y else True
    ordini = {idp: dict(zip(['colli_richiesti', 'specifica'], [colli, spec]))
              for [idu, idp, colli, spec] in ordini
              if filtroif(idu, id_utente)
              }

    prodotti = []
    pacchi = dict(get_colli_totali_pacchi(id_produttore))
    for prodotto in get_prodotti(id_produttore, disponibile=True):
        tdp = dict(prodotto)
        tdp.update({'colli_rimasti':
                    tdp['colli_disponibili'] -
                    _get_totale_ordinati(id_produttore, tdp['id'])
                    if tdp['colli_disponibili'] != 0 else -1
                    })
        if tdp['id'] in ordini.keys():
            tdp.update(ordini[tdp['id']])
            tdp.update({'prezzo_totale':
                        ordini[tdp['id']]['colli_richiesti']*tdp['prezzo']})
        if tdp['id'] in pacchi.keys():
            tdp.update({'totale_ordinati': pacchi[tdp['id']]})
        prodotti.append(tdp)

    return prodotti


def get_prodotti_ordinati(id_produttore, id_utente=None):
    """ Ritorna tutti i prodotti ordinati da id_produttore, ordinati per
        username, categoria, descrizione_prodotto
    """

    ordini = get_ordini_in_corso(id_produttore)

    prodotti_ordinati = list(filter(lambda p: 'colli_richiesti' in p.keys(),
                                    get_prodotti_ordinati_da_tutti(
                                        id_produttore, id_utente)))
    _aggiungi_dettaglio_pacchi_inconclusi(ordini, prodotti_ordinati)

    return prodotti_ordinati


def _aggiungi_dettaglio_pacchi_inconclusi(ordini, prodotti_ordinati):
    # ordini[N]: id_utente, id_prodotto, colli_richiesti, specifica
    # prodotti_ordinati[N]: 'id', 'categoria', 'disponibile',
    # 'descrizione_prodotto', 'dettaglio_qta', 'prezzo', 'n_min_colli',
    # 'n_max_colli', 'colli_disponibili', 'nota', 'colli_rimasti',
    # 'colli_richiesti', 'specifica', 'totale_ordinati'

    for prodotto in prodotti_ordinati:
        # prodotti che non fanno parte di un pacco chiuso
        pending = prodotto['colli_richiesti'] % prodotto['n_min_colli']
        # NB: 'totale_ordinati' presente solo se ordine a pacchi
        if pending != 0:
            pending = prodotto['totale_ordinati'] % prodotto['n_min_colli']
            pid = prodotto['id']
            # scansiona tutti gli ordini del prodotto in esame
            for ordine in list(filter(lambda o, pid=pid:
                                      o['id_prodotto'] == pid, ordini)):
                eccedenza = ordine['colli_richiesti'] % prodotto['n_min_colli']
                if eccedenza > 0:
                    if ordine['id_utente'] == g.user['id']:
                        prodotto.update({'pending': pending})


def _get_archivio_ordini(limit=None):
    # Non presenti in tabella dettagli_ordini, ma solo se si tratta di
    # acquisti, ovvero con tipologia = 4 (vedi tabella tipologie_movimenti)
    query = """
        SELECT storico_ordini.id as id_storico,
                consegna, importo, nome, prodotto_principale
        FROM storico_ordini INNER JOIN produttori
                    ON produttori.id = id_produttore
        WHERE id_utente = %s
        ORDER BY consegna DESC
        """
    if limit:
        query += 'LIMIT ' + str(limit)

    get_db().execute(query, [g.user['id']])

    return get_db().fetchall()


def _get_totale_ordinati(id_produttore, id_prodotto, notmine=False):
    query = """
            SELECT SUM(colli_richiesti) as totale_ordinati
            FROM ordine_in_corso_{0}
            WHERE id_prodotto = %s
            """.format(id_produttore)

    if notmine:
        query += 'AND id_utente != {0}'.format(g.user['id'])

    get_db().execute(query, (id_prodotto, ))
    totale = get_db().fetchone()['totale_ordinati']
    return totale if totale else 0


def _check_inputs_vincoli(id_produttore, inputs):
    # Credito sufficente
    dbi = get_db()

    # Utenza Attiva
    dbi.execute(
        'SELECT id FROM utenti WHERE id = %s AND attivo = TRUE',
        (g.user['id'],)
    )

    if dbi.rowcount < 1:
        return {'error_msg':
                'Spiacente, non risulti un utente attivo.'
                ' Tesseramento effettuato correttamente?'}

    # dal totale temporaneo tolgo l'ordine vecchio se presente del produttore
    # in questione
    dbi.execute(
        """
            SELECT SUM(prezzo*colli_richiesti) as totale
            FROM ordine_in_corso_{0} INNER JOIN listino_{0}
                ON listino_{0}.id = id_prodotto
            WHERE id_utente = %s
        """.format(id_produttore), (g.user['id'],))
    in_corso = dbi.fetchone()
    in_corso = float(in_corso['totale']) if in_corso['totale'] else 0
    colli_richiesti = [int(cr) if cr else 0 for cr in
                       inputs.getlist('colli_richiesti')]

    if (get_totale_utente_temporaneo() + in_corso) < sum([
        float(p)*float(cr) for p, cr in zip(
            inputs.getlist('prezzo'), colli_richiesti
        )
    ]):
        return {'error_msg':
                'Credito insufficente per coprire tutti gli ordini.'
                ' Vai alla voce Ricarica per accreditare con carta.'}

    for i, prodotto in enumerate(get_prodotti(id_produttore,
                                              disponibile=True)):
        # Superamento n_max_colli
        if (prodotto['n_max_colli'] != 0 and
                colli_richiesti[i] > prodotto['n_max_colli']):
            return {'error_msg':
                    ' '.join(['Colli Massimi per Gasista:',
                              str(prodotto['n_max_colli']),
                              'ne hai ordinati',
                              str(colli_richiesti[i])])
                    }

        # Superamento colli_disponibili (singolo utente)
        if (prodotto['colli_disponibili'] != 0 and
                colli_richiesti[i] > prodotto['colli_disponibili']):
            return {'error_msg':
                    ' '.join(['Il numero di colli ordinati di',
                              prodotto['descrizione_prodotto'], '(',
                              colli_richiesti[i], ') eccede la disponibilità',
                              'del produttore (',
                              str(prodotto['colli_disponibili']), ')'])
                    }

        # Superamento colli_disponibili (tutti gli utenti)
        ordinati = _get_totale_ordinati(id_produttore, prodotto['id'])
        if (prodotto['colli_disponibili'] > 0 and
                ordinati > prodotto['colli_disponibili']):
            return {'error_msg': 'Esaurita disponibilità per ' +
                                 prodotto['descrizione_prodotto']
                    }

    return {}


def _inserisci_rettifica(id_utente, id_produttore, importo, motivazione,
                         consegna):
    """ Inserisce la rettifica nei movimenti e nello storico """
    dbi = get_db()
    id_utente = int(id_utente)

    dbi.execute("SELECT nome FROM produttori WHERE id = %s", (id_produttore,))
    nome_produttore = dbi.fetchone()['nome']

    dbi.execute("""
        SELECT id_utente,
               json_agg(json_build_array(colli_richiesti,
               descrizione_prodotto, dettaglio_qta, prezzo)) AS dettaglio
        FROM ordine_in_corso_{0} INNER JOIN listino_{0} ON
             ordine_in_corso_{0}.id_prodotto = listino_{0}.id
        GROUP BY id_utente
        """.format(id_produttore))
    dettagli_prodotti = dict(dbi.fetchall())

    motivazione = ' '.join(
        ['Acquisto', '(', motivazione, ')']) if motivazione else 'Acquisto'

    dbi.execute("""
        INSERT INTO movimenti
            (per_id_utente, importo, descrizione, effettuato_il)
        VALUES (%s, %s, %s, %s)
          RETURNING id
        """, (id_utente, -float(importo), motivazione, datetime.now())
    )

    id_movimento = dbi.fetchone()['id']

    if id_utente in dettagli_prodotti.keys():
        dettaglio_completo = {
            'produttore': nome_produttore,
            'dettaglio': dettagli_prodotti[id_utente]
        }
    else:
        dettaglio_completo = {
            'produttore': nome_produttore,
            'dettaglio': motivazione
        }

    dbi.execute("""
        INSERT INTO storico_ordini
        (id_utente, id_produttore, importo, consegna, dettaglio, id_movimento)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_utente, id_produttore, -float(importo), consegna,
              json.dumps(dettaglio_completo), id_movimento)
    )


def _pagamenti_ordini_chiusi():
    dbi = get_db()
    dbi.execute("""
        SELECT id_produttore, nome as nome_produttore,
               SUM(importo) as totale, consegna
        FROM storico_ordini
            INNER JOIN produttori
                ON produttori.id = storico_ordini.id_produttore
        GROUP BY id_produttore, nome, consegna
        ORDER BY consegna DESC
    """)
    ordini_chiusi = dbi.fetchall()
    dbi.execute("""
        SELECT id, id_produttore, consegna, data_pagamento
        FROM pagamenti_ordini
        ORDER BY consegna DESC
    """)
    pagamenti = dbi.fetchall()

    pagamenti_ordini_chiusi = []
    pagamenti = {''.join([str(p[1]), str(p[2])]):
                 {'id_pagamento': p[0], 'data_pagamento': p[3]}
                 for p in pagamenti}

    for ordine in ordini_chiusi:
        k = ''.join([str(ordine['id_produttore']), str(ordine['consegna'])])
        if k in pagamenti.keys():
            pagamenti_ordini_chiusi.append({
                'id_pagamento': pagamenti.get(k)['id_pagamento'],
                'nome_produttore': ordine['nome_produttore'],
                'totale': ordine['totale'],
                'consegna': ordine['consegna'],
                'data_pagamento': pagamenti.get(k)['data_pagamento']
            })

    return pagamenti_ordini_chiusi


def _delete(id_produttore):
    # Pulisco (TRUNCATE) la tabella ordine_in_corso_ID-PRODUTTORE
    # Rimuovo (DELETE) la riga associata in dettagli_ordini
    get_db().execute("""
        TRUNCATE ordine_in_corso_{0} ;
        DELETE FROM dettagli_ordini WHERE id_produttore = %s ;
        """.format(id_produttore), [id_produttore])


def _get_dettaglio(id_produttore):
    get_db().execute("""
        SELECT scadenza, consegna, minimo_ordine, nota
        FROM dettagli_ordini
        WHERE id_produttore = %s
    """, [id_produttore])
    dettaglio = get_db().fetchone()

    if dettaglio is None:  # Non vi sono ordini aperti
        # preparo la struttura per jinja, che accede alle keys
        dettaglio = {'scadenza': '', 'consegna': '',
                     'minimo_ordine': '', 'nota': ''}

    return dettaglio


def get_colli_totali_pacchi(id_produttore):
    """ Ritorna una lista di (id_prodotto, totali_ordinati) dove
        totali_ordinati corrisponde al numero di colli richiesti da tutti gli
        utenti, in questo modo è possibile determinare quanti colli mancano per
        chiudere un pacco """
    get_db().execute("""
        SELECT id_prodotto, SUM(colli_richiesti) as totali_ordinati
        FROM ordine_in_corso_{0} INNER JOIN
             (SELECT * FROM listino_{0} WHERE n_min_colli > 1) AS pacchi
             ON pacchi.id = id_prodotto
        GROUP BY id_prodotto;
        """.format(id_produttore))

    return get_db().fetchall()


def get_minimo_ordine(id_produttore):
    """ Ritorna il minimo_ordine corrente """
    get_db().execute('SELECT minimo_ordine FROM dettagli_ordini'
                     ' WHERE id_produttore = %s', (id_produttore,))
    minimo_ordine = get_db().fetchone()['minimo_ordine']
    # If NULL return default 0, per jinja
    return minimo_ordine if minimo_ordine else 0


def get_produttore(id_produttore):
    """ Ritorna il produttore associato a id_produttore """
    get_db().execute('SELECT id, nome FROM produttori WHERE id = %s',
                     (id_produttore,))
    return get_db().fetchone()


def msg_presidio():
    """ Ritorna il messaggio da dare in merito i presidi """
    presidi = get_presidi()
    datep = [p[0] for p in presidi if p[1] == g.user['id']]
    msg = ''

    if not any([g.ruoli, g.referenze]):
        # Non ho ne ruoli ne referenze quindi devo presidiare
        prenotazioni = len(datep)
        if prenotazioni < 1:
            return "Non hai ancora scelto due date di presidio, ricorda che " \
                "è invitato partecipare come minimo a due presidi per" \
                " essere un vero membro del GAS"
        if prenotazioni == 1:
            msg = "Hai ancora un presidio da prenotare, non rimandare."

    imminente = [d for d in datep
                 if -1 < (d - datetime.now()).days < 14]
    if imminente:
        return ' '.join([msg,
                        "Ricordati che hai un presidio",
                         "nelle date:" if len(imminente) > 1 else "in data:",
                         ', '.join([d.strftime("%d/%m/%Y") for d in imminente])
                         ])

    return None


def rimuovi_ordini_inconclusi(dettagli_ordini):
    """ Rimuove gli ordini che non hanno raggiunto il minimo_ordine dopo la
    data di scadenza """
    for dett in dettagli_ordini:
        mino = float(dett['minimo_ordine'])
        if (dett['scadenza'] < datetime.today() and mino > 0 and mino >
                sum(get_spesa_totale_utenti(dett['id_produttore']).values())):
            _delete(dett['id_produttore'])


def rimuovi_pacchi_inconclusi(dettagli_ordini):
    """ Rimuove gli ordini, di ogni singolo produttore, che non hanno raggiunto
    il n_min_colli (corrispondono ai pacchi non chiusi), se la data di scadenza
    è stata raggiunta """
    dbi = get_db()

    for dettaglio_ordine in dettagli_ordini:

        id_produttore = dettaglio_ordine['id_produttore']

        dbi.execute("""
            SELECT * FROM
                (SELECT id_prodotto, SUM(colli_richiesti) as ordinati,
                        n_min_colli
                 FROM ordine_in_corso_{0} INNER JOIN listino_{0}
                    ON listino_{0}.id = id_prodotto
                 WHERE n_min_colli > 1
                 GROUP BY id_prodotto, n_min_colli) t
            ORDER BY id_prodotto
            """.format(id_produttore))
        ordini_aggregati = dbi.fetchall()

        da_rimuovere = [o['id_prodotto'] for o in filter(
            lambda oa: oa['ordinati'] < oa['n_min_colli'],
            ordini_aggregati)]
        dbi.execute("""
                DELETE FROM ordine_in_corso_{0}
                WHERE id_prodotto = ANY(%s)""".format(id_produttore),
                    (da_rimuovere,))

        prodotti_da_aggiornare = [
            {'id_prodotto': o['id_prodotto'],
                'eccedenze': o['ordinati'] % o['n_min_colli'],
             'n_min_colli': o['n_min_colli']
             } for o in filter(lambda oa: oa['ordinati'] > oa['n_min_colli']
                               and oa['ordinati'] % oa['n_min_colli'] > 0,
                               ordini_aggregati)
        ]

        for prodotto in prodotti_da_aggiornare:
            dbi.execute(
                """
                SELECT id, id_prodotto, colli_richiesti
                FROM ordine_in_corso_{0}
                WHERE id_prodotto = %s
                ORDER BY effettuato_il DESC
                """.format(id_produttore), (prodotto['id_prodotto'],))
            ordini_da_aggiornare = dbi.fetchall()

            for ordine in ordini_da_aggiornare:
                if ordine['colli_richiesti'] % prodotto['n_min_colli'] == 0:
                    continue
                if ordine['colli_richiesti'] <= prodotto['eccedenze']:
                    dbi.execute(
                        'DELETE FROM ordine_in_corso_{0} WHERE id = %s'
                        .format(id_produttore), (ordine['id'],))
                    prodotto['eccedenze'] -= ordine['colli_richiesti']
                    if prodotto['eccedenze'] == 0:
                        break
                else:
                    dbi.execute(
                        """
                        UPDATE ordine_in_corso_{0}
                        SET colli_richiesti = %s WHERE id = %s
                    """.format(id_produttore),
                        (ordine['colli_richiesti'] - prodotto['eccedenze'],
                         ordine['id']))
                    break

    return dettagli_ordini


def sollecito(func):
    """ Richiesta di informazioni obbligatorie agli utenti """
    @wraps(func)
    def decorated_function(*args, **kwargs):
        utente = get_utente_by_id(g.user['id'])
        for obbligatorio in [utente['nome'], utente['cognome'],
                             utente['email'], utente['cf']]:
            if not obbligatorio:
                nome_associazione = current_app.config['ASSOCIAZIONE'][
                    'identita']['nome']
                flash("""È richiesto compilare i campi: nome, cognome, email e
                codice fiscale, ai fini di redigere il libro soci della
                {0}""".format(nome_associazione), 'warning')
                return redirect(url_for('auth.info_utente'))
        return func(*args, **kwargs)
    return decorated_function
