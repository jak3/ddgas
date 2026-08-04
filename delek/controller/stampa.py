'''Gestione delle stampe'''

from io import BytesIO

from flask import Blueprint, flash, g, render_template, request, send_file

from delek.controller.auth import login_required, is_ruolo
from delek.controller.db import get_db
from delek.controller.db_wrapper import get_spesa_totale_utenti
from delek.controller.produttori import get_storico_ordini, get_produttore
from delek.controller.tempo import adesso, da_form

bp = Blueprint('stampa', __name__, url_prefix='/stampa')


def get_date_ordine(id_produttore):
    """Ritorna le date di scadenza e consegna dell'ordine in corso per
    id_produttore"""
    get_db().execute(
        """
        SELECT scadenza, consegna, now() as now
        FROM dettagli_ordini WHERE id_produttore = %s
        """,
        (id_produttore,),
    )

    return get_db().fetchone()


def get_consegne(id_produttore):
    """Ritorna l'elenco delle consegne effettuate da `id_produttore`"""
    get_db().execute(
        """
            SELECT consegna FROM storico_ordini
            WHERE id_produttore = %s
            GROUP BY consegna ORDER BY consegna DESC
        """,
        [id_produttore],
    )
    return get_db().fetchall()


def get_prodotti_ordinati_dettaglio(id_produttore, id_utente=None):
    """Ritorna tutti i prodotti ordinati da id_produttore, ordinati per
    username, categoria, descrizione_prodotto
    """
    column_names = [
        'categoria',
        'colli_richiesti',
        'descrizione_prodotto',
        'dettaglio_qta',
        'id_utente',
        'n_min_colli',
        'nota',
        'prezzo',
        'specifica',
        'totale_ordinati',
        'id_prodotto',
    ]

    if not id_utente:
        column_names += ['cognome', 'email', 'nome', 'username']
        get_db().execute("""
        SELECT {column_names}
        FROM ordine_in_corso_{idp} INNER JOIN utenti ON id_utente = utenti.id
                INNER JOIN listino_{idp} ON listino_{idp}.id = id_prodotto
                INNER JOIN (SELECT id_prodotto AS _id_prodotto,
                                   SUM(colli_richiesti) as totale_ordinati
                            FROM ordine_in_corso_{idp}
                            GROUP BY id_prodotto
                           ) AS sub ON id_prodotto = sub._id_prodotto
        WHERE colli_richiesti > 0
        ORDER BY username, categoria, descrizione_prodotto
        """.format(column_names=', '.join(column_names), idp=id_produttore))
    else:
        get_db().execute(
            """
        SELECT {column_names}
        FROM ordine_in_corso_{idp} INNER JOIN listino_{idp}
                    ON listino_{idp}.id = id_prodotto
                INNER JOIN (SELECT id_prodotto AS _id_prodotto,
                                   SUM(colli_richiesti) as totale_ordinati
                            FROM ordine_in_corso_{idp}
                            GROUP BY id_prodotto
                           ) AS sub ON id_prodotto = sub._id_prodotto
        WHERE colli_richiesti > 0 AND id_utente = %s
        ORDER BY categoria, descrizione_prodotto
        """.format(column_names=', '.join(column_names), idp=id_produttore),
            (id_utente,),
        )

    return get_db().fetchall()


def get_riepilogo_prodotti(id_produttore):
    """Ritorna i dati utili alla stampa del riepilogo per l'ordine in corso di
    id_produttore
    """
    get_db().execute(f"""
        SELECT id_prodotto, categoria, descrizione_prodotto, dettaglio_qta,
                prezzo, nota, n_min_colli,
                SUM(colli_richiesti) as totale_ordinati
        FROM ordine_in_corso_{id_produttore} INNER JOIN listino_{id_produttore}
                ON listino_{id_produttore}.id = id_prodotto
        GROUP BY id_prodotto, categoria, descrizione_prodotto, dettaglio_qta,
                 prezzo, nota, n_min_colli
        ORDER BY categoria, descrizione_prodotto
        """)
    return get_db().fetchall()


def get_totale_prodotti_ordinati(prodotti):
    """Ritorna il totale dell'ordine, calcolato moltiplicando i numeri dei
    colli_richiesti per il prezzo cad
    """
    return sum(p['prezzo'] * p['colli_richiesti'] for p in prodotti)


def get_storico(id_produttore, consegna):
    """Ritorna tutti gli ordini fatti da id_produttore in una data di consegna
    passata come parametro. Se non indicata, si suppone l'ultima consegna"""
    get_db().execute(
        """
        SELECT consegna, dettaglio
        FROM storico_ordini
        WHERE id_produttore = %s and consegna = %s
        """,
        (id_produttore, consegna),
    )
    return get_db().fetchall()


def _dettagli_ordini(id_produttore, template):
    date_ordine = get_date_ordine(id_produttore)
    prodotti_ordinati = []
    if date_ordine:
        prodotti_ordinati = get_prodotti_ordinati_dettaglio(id_produttore)
    # else: # ordine chiuso (rettifiche già fatte), stampa dello storico
    # alternativa a funzione riepilogo?

    return render_template(
        template,
        date_ordine=date_ordine,
        prodotti_ordinati=prodotti_ordinati,
        produttore=get_produttore(id_produttore),
        riepilogo_prodotti=get_riepilogo_prodotti(id_produttore),
        totale=get_totale_prodotti_ordinati(prodotti_ordinati),
        totali_utenti=get_spesa_totale_utenti(id_produttore),
    )


@bp.route('/dettagli/<int:id_produttore>')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def dettagli_ordini(id_produttore):
    """Per moderatori e referenti permette di avere un riassunto di tutti gli
    ordini effettuati, elenco dei singoli utenti seguito da un recap generale
    """
    return _dettagli_ordini(id_produttore, 'stampa/dettagli_all.html')


@bp.route('/dettagli/<int:id_produttore>/utente')
@login_required
def dettagli_ordini_utente(id_produttore):
    """Dettaglio ordine di un utente"""
    prodotti_ordinati = get_prodotti_ordinati_dettaglio(id_produttore, g.user['id'])
    return render_template(
        'stampa/dettagli_utente.html',
        date_ordine=get_date_ordine(id_produttore),
        prodotti_ordinati=prodotti_ordinati,
        produttore=get_produttore(id_produttore),
        totale=get_totale_prodotti_ordinati(prodotti_ordinati),
    )


@bp.route('/dettagli/<int:id_produttore>/utenti')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def dettagli_ordini_con_utenti(id_produttore):
    """Riassunto dell'ordine di tutti gli utenti, con una formattazione
    agibile per essere stampata
    """
    return _dettagli_ordini(id_produttore, template='stampa/riepilogo.html')


@bp.route('/dettagli/<int:id_produttore>/utenti/tiny')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def dettagli_ordini_con_utenti_tiny(id_produttore):
    """Riassunto dell'ordine di tutti gli utenti, con una formattazione
    compatta e agibile per essere stampata
    """
    return _dettagli_ordini(id_produttore, template='stampa/tiny/riepilogo.html')


def _esporta_to_csv(fname, query):
    content = BytesIO()
    get_db().copy_expert(query, content)
    content.seek(0)
    return send_file(
        content, as_attachment=True, download_name=f'{fname}.csv', mimetype='text/csv'
    )


@bp.route('esporta/dettagli/<int:id_produttore>/utenti')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def esporta_riepilogo_utenti(id_produttore):
    """Esporta in formato csv il riepilogo utenti di un dettaglio ordine"""
    return _esporta_to_csv(
        "riepilogo-utenti-"
        + get_produttore(id_produttore, column_names=['nome'])['nome'],
        """COPY ( SELECT descrizione_prodotto,
                           dettaglio_qta, n_min_colli, colli_richiesti, prezzo,
                to_char(colli_richiesti*prezzo, 'FM999999999.00') as totale,
                nota, specifica, username, nome, cognome
        FROM ordine_in_corso_{idp} INNER JOIN utenti ON id_utente = utenti.id
                INNER JOIN listino_{idp} ON listino_{idp}.id = id_prodotto
        WHERE colli_richiesti > 0
        ORDER BY username, descrizione_prodotto) TO STDOUT
        WITH CSV HEADER
        """.format(idp=id_produttore),
    )


@bp.route('esporta/dettagli/<int:id_produttore>/generale')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def esporta_riepilogo_generale(id_produttore):
    """Esporta in formato csv il riepilogo generale di un dettaglio ordine"""
    return _esporta_to_csv(
        "riepilogo-generale-"
        + get_produttore(id_produttore, column_names=['nome'])['nome'],
        f"""COPY (
        SELECT  descrizione_prodotto, dettaglio_qta, prezzo, nota, n_min_colli,
                SUM(colli_richiesti) as totale_ordinati
        FROM ordine_in_corso_{id_produttore} INNER JOIN listino_{id_produttore}
                ON listino_{id_produttore}.id = id_prodotto
        GROUP BY  descrizione_prodotto, dettaglio_qta, prezzo, nota,
                  n_min_colli
        ORDER BY descrizione_prodotto ) TO STDOUT WITH CSV HEADER
        """,
    )


@bp.route('/dettagli/<int:id_produttore>/generale')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def dettagli_ordini_generale(id_produttore):
    """Riepilogo generico dell'ordine con una formattazione agibile per essere
    stampata
    """
    return render_template(
        'stampa/riepilogo-generale.html',
        date_ordine=get_date_ordine(id_produttore),
        produttore=get_produttore(id_produttore),
        riepilogo_prodotti=get_riepilogo_prodotti(id_produttore),
        totale=get_totale_prodotti_ordinati(
            get_prodotti_ordinati_dettaglio(id_produttore)
        ),
    )


@bp.route('/dettagli/<int:id_produttore>/generale/tiny')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def dettagli_ordini_generale_tiny(id_produttore):
    """Riepilogo generico dell'ordine con una formattazione compatta e agibile
    per essere stampata
    """
    return render_template(
        'stampa/tiny/riepilogo-generale.html',
        date_ordine=get_date_ordine(id_produttore),
        produttore=get_produttore(id_produttore),
        riepilogo_prodotti=get_riepilogo_prodotti(id_produttore),
        totale=get_totale_prodotti_ordinati(
            get_prodotti_ordinati_dettaglio(id_produttore)
        ),
    )


@bp.route('/storico/<int:id_produttore>')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def storico(id_produttore):
    """Stampa una versione stampabile di un'ordine nello storico"""
    # Se GET, seleziono di default l'ultima
    consegna = None
    try:
        if 'data' in request.args.keys():
            consegna = da_form(request.args.get('data'))
        else:
            consegna = get_consegne(id_produttore)[0]['consegna']
    except ValueError:
        error = 'Formato data non riconosciuto'
        flash(error, 'warning')
    ordini = get_storico_ordini(id_produttore, consegna)

    return render_template(
        'stampa/storico.html',
        date_ordine={'consegna': consegna},
        ordini=ordini,
        produttore=get_produttore(id_produttore),
        totale=sum(o['importo'] for o in ordini),
    )


@bp.route('/storico/<int:id_produttore>/tiny')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def storico_tiny(id_produttore):
    """Stampa una versione stampabile compatta di un'ordine nello storico"""
    # Se GET, seleziono di default l'ultima
    consegna = None
    try:
        if 'data' in request.args.keys():
            consegna = da_form(request.args.get('data'))
        else:
            consegna = get_consegne(id_produttore)[0]['consegna']
    except ValueError:
        error = 'Formato data non riconosciuto'
        flash(error, 'warning')
    ordini = get_storico_ordini(id_produttore, consegna)

    return render_template(
        'stampa/tiny/storico.html',
        date_ordine={'consegna': consegna},
        ordini=ordini,
        produttore=get_produttore(id_produttore),
        totale=sum(o['importo'] for o in ordini),
    )


def get_tutti_ordini():
    """Ritorna tutti gli ordini attivi per i produttori che consegnano oggi,
    organizzati gerarchicamente per produttore e utente"""
    db = get_db()

    db.execute("""
        SELECT p.id, p.nome
        FROM produttori p
        JOIN dettagli_ordini d ON p.id = d.id_produttore
        WHERE p.attivo = TRUE
        AND DATE(d.consegna) = DATE(now() at time zone 'Europe/Rome')
    """)
    produttori = db.fetchall()

    # Dizionario per organizzare i dati gerarchicamente
    ordini_per_produttore = {}

    # Per ogni produttore, otteniamo i dettagli degli ordini
    for produttore in produttori:
        id_produttore = produttore['id']
        nome_produttore = produttore['nome']

        db.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'ordine_in_corso_%s'
            )
        """,
            (id_produttore,),
        )

        tabella_esiste = db.fetchone()['exists']

        if not tabella_esiste:
            continue

        db.execute(f"""
            SELECT
                u.id as id_utente,
                u.nome as nome_utente,
                u.cognome as cognome_utente,
                u.username,
                l.descrizione_prodotto,
                l.dettaglio_qta,
                o.colli_richiesti,
                o.specifica
            FROM ordine_in_corso_{id_produttore} o
            INNER JOIN utenti u ON o.id_utente = u.id
            INNER JOIN listino_{id_produttore} l ON o.id_prodotto = l.id
            WHERE o.colli_richiesti > 0
            ORDER BY u.cognome, u.nome, l.descrizione_prodotto
        """)

        ordini_produttore = db.fetchall()

        if not ordini_produttore:
            continue

        # Organizziamo gli ordini per utente
        ordini_per_utente = {}
        for ordine in ordini_produttore:
            id_utente = ordine['id_utente']
            ns = f"{ordine['cognome_utente']} {ordine['nome_utente']}"

            if id_utente not in ordini_per_utente:
                ordini_per_utente[id_utente] = {'nome_completo': ns, 'prodotti': []}

            ordini_per_utente[id_utente]['prodotti'].append(
                {
                    'descrizione': ordine['descrizione_prodotto'],
                    'dettaglio': ordine['dettaglio_qta'],
                    'quantita': ordine['colli_richiesti'],
                    'specifica': ordine['specifica'],
                }
            )

        # Aggiungiamo al dizionario principale
        ordini_per_produttore[nome_produttore] = ordini_per_utente

    return ordini_per_produttore


@bp.route('/dettagli_in_consegna')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def dettagli_in_consegna():
    """Stampa i dettagli di tutti gli ordini che consegnano oggi"""
    ordini_per_produttore = get_tutti_ordini()

    return render_template(
        'stampa/dettagli_in_consegna.html',
        ordini_per_produttore=ordini_per_produttore,
        now=adesso(),
    )


@bp.route('/esporta/tutti_dettagli')
@login_required
@is_ruolo(['moderatore', 'referente', 'presidiante'])
def esporta_tutti_dettagli():
    """Esporta in CSV i dettagli di tutti gli ordini attivi"""
    db = get_db()

    db.execute("""
        SELECT p.id, p.nome
        FROM produttori p
        JOIN dettagli_ordini d ON p.id = d.id_produttore
        WHERE p.attivo = TRUE
        AND DATE(d.consegna) = DATE(now() at time zone 'Europe/Rome')
    """)
    produttori = db.fetchall()

    # Creiamo una tabella temporanea per raccogliere tutti i dati
    db.execute("""
        CREATE TEMPORARY TABLE temp_tutti_ordini (
            nome TEXT,
            cognome TEXT,
            username TEXT,
            nome_produttore TEXT,
            descrizione_prodotto TEXT,
            dettaglio_qta TEXT,
            colli_richiesti INTEGER,
            specifica TEXT
        )
    """)

    # Per ogni produttore, inseriamo i dati nella tabella temporanea
    for produttore in produttori:
        id_produttore = produttore['id']

        db.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'ordine_in_corso_%s'
            )
        """,
            (str(id_produttore),),
        )

        tabella_esiste = db.fetchone()['exists']

        if not tabella_esiste:
            continue

        # Inseriamo i dati nella tabella temporanea
        db.execute(f"""
            INSERT INTO temp_tutti_ordini
            SELECT
                u.nome,
                u.cognome,
                u.username,
                p.nome as nome_produttore,
                l.descrizione_prodotto,
                l.dettaglio_qta,
                o.colli_richiesti,
                o.specifica
            FROM ordine_in_corso_{id_produttore} o
            INNER JOIN utenti u ON o.id_utente = u.id
            INNER JOIN listino_{id_produttore} l ON o.id_prodotto = l.id
            INNER JOIN produttori p ON p.id = {id_produttore}
            WHERE o.colli_richiesti > 0
        """)

    # Esportiamo la tabella temporanea in CSV
    return _esporta_to_csv(
        "tutti-dettagli-ordini",
        """COPY (
                                SELECT nome, cognome, username,
                                       nome_produttore, descrizione_prodotto,
                                       dettaglio_qta, colli_richiesti,
                                       specifica
                                FROM temp_tutti_ordini
                                ORDER BY cognome, nome, nome_produttore,
                                descrizione_prodotto
                            ) TO STDOUT WITH CSV HEADER
                           """,
    )
