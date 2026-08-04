"""Gestione ordini"""

import csv
from io import StringIO, BytesIO
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
    send_file,
)

from delek.controller.tempo import adesso, da_form
from delek.model.checks import (
    check_inputs_ordine,
    check_inputs_dettagli_ordine,
    check_inputs_rettifiche,
)
from delek.controller.auth import (
    get_utente_by_id,
    get_utenti,
    login_required,
    is_ruolo,
    is_mod_or_ref_of,
)
from delek.controller.db import get_db
from delek.controller.db_wrapper import (
    get_spesa_totale_utenti,
    get_totale_utente_temporaneo,
)
from delek.controller.presidi import get_date_con_presidiante
from delek.controller.stampa import get_date_ordine, get_totale_prodotti_ordinati
from delek.controller.support_func_ordini import (
    _delete,
    _get_dettaglio,
    _get_archivio_ordini,
    _check_inputs_vincoli,
    _get_totale_ordinati,
    _inserisci_rettifica,
    _pagamenti_ordini_chiusi,
    get_prodotti_ordinati_da_tutti,
    get_prodotti_ordinati,
    get_minimo_ordine,
    get_produttore,
    msg_presidio,
    rimuovi_ordini_inconclusi,
    rimuovi_pacchi_inconclusi,
    sollecito,
)

bp = Blueprint('ordini', __name__, url_prefix='/ordini')


@bp.route('/', methods=('GET', 'POST'))
@login_required
@sollecito
def list_ordini():
    """Homepage: Elenca ordini in corso e storico degli ordini chiusi /
    archiviati
    """
    dbi = get_db()
    dbi.execute("""
            SELECT dettagli_ordini.id as id_dettaglio, id_produttore,
                scadenza, consegna, minimo_ordine, nota,
                nome as nome_produttore, prodotto_principale
            FROM dettagli_ordini INNER JOIN produttori
                ON dettagli_ordini.id_produttore = produttori.id
            ORDER BY scadenza
            """)
    dettagli_ordini = dbi.fetchall()

    da_chi_ordino = []
    for ordine in dettagli_ordini:
        dbi.execute(
            """
            SELECT id_utente FROM ordine_in_corso_{0} WHERE id_utente = %s
            """.format(ordine['id_produttore']),
            (g.user['id'],),
        )
        csono = dbi.fetchone()
        if csono is not None:
            da_chi_ordino.append(ordine['id_produttore'])

    ordini_scadenza = list(filter(lambda o: o['scadenza'] >= adesso(), dettagli_ordini))

    # Rimozione direttamente nel DB
    rimuovi_ordini_inconclusi(dettagli_ordini)

    prossime_consegne = list(
        filter(
            lambda o: o['scadenza'] < adesso() and o['consegna'] >= adesso() and
            # escludo gli ordini che non hanno raggiunto il minimo d'ordine
            float(o['minimo_ordine'])
            < sum(get_spesa_totale_utenti(o['id_produttore']).values()),
            dettagli_ordini,
        )
    )

    prossime_consegne = sorted(
        # Rimozione nella struttura dati python
        rimuovi_pacchi_inconclusi(prossime_consegne),
        key=lambda o: o['consegna'],
    )

    mie_prossime_consegne = sorted(
        list(filter(lambda o: o['id_produttore'] in da_chi_ordino, prossime_consegne)),
        key=lambda o: o['consegna'],
    )

    ordini_in_rettifica = sorted(
        list(
            filter(
                lambda o: o['consegna'] < adesso()
                and (
                    o['id_produttore'] in da_chi_ordino
                    or o['id_produttore'] in g.referenze
                    or 'moderatore' in g.ruoli
                ),
                dettagli_ordini,
            )
        ),
        key=lambda o: o['prodotto_principale'],
    )

    return render_template(
        'ordini/list.html',
        da_chi_ordino=da_chi_ordino,
        mie_prossime_consegne=mie_prossime_consegne,
        ordini_archivio=_get_archivio_ordini(10),
        ordini_in_rettifica=ordini_in_rettifica,
        ordini_scadenza=ordini_scadenza,
        prenotati=get_date_con_presidiante(),
        prossime_consegne=prossime_consegne,
        totale=get_totale_utente_temporaneo(),
        msg_presidio=msg_presidio(),
    )


@bp.route('/chiusi')
@login_required
def chiusi():
    """Elenca tutti gli ordini chiusi, utili ai tesorieri per controllare e
    rintracciare le fatture non ancora pagate"""
    return render_template(
        'ordini/chiusi.html', pagamenti_ordini_chiusi=_pagamenti_ordini_chiusi()
    )


@bp.route('/pagamento/<int:id_pagamento>', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def pagamento(id_pagamento):
    """Permette di impostare la data di pagamento di un ordine chiuso"""
    error = None
    if request.method == 'POST':
        try:
            datetime.fromisoformat(request.form['data_pagamento'])
        except ValueError:
            error = {'error_msg': u'Formato date non conforme'}
        if not error:
            get_db().execute(
                """
                UPDATE pagamenti_ordini SET data_pagamento = %s
                WHERE id = %s
            """,
                (request.form['data_pagamento'], id_pagamento),
            )
            return redirect(url_for('ordini.chiusi'))

        flash(error['error_msg'], 'warning')

    return render_template('ordini/pagamento.html')


@bp.route('/chiusi/esporta')
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def esporta():
    """Esporta elenco degli ordini chiusi"""
    content = StringIO()
    pagamenti_ordini_chiusi = _pagamenti_ordini_chiusi()
    writer = csv.DictWriter(content, fieldnames=pagamenti_ordini_chiusi[0].keys())
    writer.writeheader()
    writer.writerows(pagamenti_ordini_chiusi)
    mem = BytesIO()
    mem.write(content.getvalue().encode())
    mem.seek(0)
    content.close()
    return send_file(
        mem, as_attachment=True, download_name='ordini-chiusi.csv', mimetype='text/csv'
    )


@bp.route('/archivio')
@login_required
def list_archivio():
    """Elenca tutti gli ordini archiviati"""
    return render_template(
        'ordini/archivio.html', ordini_archivio=_get_archivio_ordini()
    )


@bp.route('/effettua/<int:id_produttore>', methods=('GET', 'POST'))
@login_required
def effettua_ordine(id_produttore):
    """Elenco prodotti con form per acquisto in riferimento all'utente in
    sessione e il produttore con id_produttore
    """
    dbi = get_db()
    error = None
    msg = ''

    if request.method == 'POST':
        error = check_inputs_ordine(request.form) or _check_inputs_vincoli(
            id_produttore, request.form
        )

        if not error:
            # Elimino tutti gli ordini precedenti dell'utente corrente
            dbi.execute(
                'DELETE FROM ordine_in_corso_{0} WHERE id_utente = %s'.format(
                    id_produttore
                ),
                (g.user['id'],),
            )

            # Aggiungo i nuovi ordini, solo se i colli sono > 0
            for id_prodotto, colli_richiesti, specifica in filter(
                lambda row: int(row[1] if row[1] else 0) > 0,
                zip(
                    request.form.getlist('id_prodotto'),
                    request.form.getlist('colli_richiesti'),
                    request.form.getlist('specifica'),
                ),
            ):
                dbi.execute(
                    'SELECT colli_disponibili FROM listino_{0} WHERE id = %s'.format(
                        id_produttore
                    ),
                    (id_prodotto,),
                )
                disponibili = dbi.fetchone()['colli_disponibili']
                # Prima di inserire, controllo se il produttore ha un limite di
                # disponibilità per il prodotto, ordino il massimo possibile in
                # base alla richiesta
                if disponibili > 0:
                    ordini = _get_totale_ordinati(
                        id_produttore, id_prodotto, notmine=True
                    )
                    if ordini + int(colli_richiesti) > disponibili:
                        msg = ' '.join(
                            [
                                '(ordinati',
                                str(disponibili - ordini),
                                'al posto di',
                                colli_richiesti,
                                'per disponibilità massima raggiunta)',
                            ]
                        )
                        colli_richiesti = disponibili - ordini

                if int(colli_richiesti) > 0:
                    dbi.execute(
                        """
                        INSERT INTO ordine_in_corso_{0}
                        (id_utente, id_prodotto, colli_richiesti, specifica)
                        VALUES
                        (%s, %s, %s, %s)""".format(id_produttore),
                        (g.user['id'], id_prodotto, colli_richiesti, specifica),
                    )

            msg += ' '.join(
                [
                    '·',
                    'Totale Provvisorio:',
                    '%.2f'
                    % (
                        get_totale_prodotti_ordinati(
                            get_prodotti_ordinati(id_produttore, g.user['id'])
                        )
                    ),
                    '€',
                ]
            )

            flash('Aggiornamento Ordine avvenuto con Successo ' + msg, 'success')

    if error:
        flash(error['error_msg'], 'warning')

    return render_template(
        'ordini/effettua.html',
        date_ordine=get_date_ordine(id_produttore),
        minimo_ordine=get_minimo_ordine(id_produttore),
        prodotti=get_prodotti_ordinati_da_tutti(id_produttore, g.user['id']),
        prodotti_ordinati=get_prodotti_ordinati(id_produttore, g.user['id']),
        produttore=get_produttore(id_produttore),
        totale=get_totale_utente_temporaneo(),
        totale_ordine=sum(get_spesa_totale_utenti(id_produttore).values()),
    )


@bp.route('/create', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def create():
    """Crea un nuovo ordine"""
    dbi = get_db()

    if request.method == 'POST':
        error = check_inputs_dettagli_ordine(request.form)

        if 'scadenza' not in request.form and 'consegna' not in request.form:
            error = {'error_msg': 'Date di scadenza e consegna richieste'}

        try:
            if any(
                adesso() > d
                for d in [
                    (da_form(request.form['scadenza']) + timedelta(hours=22)),
                    (da_form(request.form['consegna']) + timedelta(hours=19)),
                ]
            ):
                error = {'error_msg': 'Non è consentito impostare date nel passato'}
        except ValueError:
            error = {'error_msg': u'Formato date non conforme'}

        if not error:
            # id_produttore è già stato validato come intero positivo da
            # check_inputs_dettagli_ordine; il cast esplicito impedisce che
            # possa finire non parametrizzato in un nome di tabella
            dbi.execute(
                'SELECT * FROM listino_{0}'.format(int(request.form['id_produttore']))
            )

            if dbi.rowcount <= 0:
                flash(
                    'Necessario prima di aprire un ordine, creare un'
                    ' listino. Comincia aggiungendo un prodotto',
                    'warning',
                )
                return redirect(
                    url_for(
                        'listini.create', id_produttore=request.form['id_produttore']
                    )
                )

            inputs = request.form.copy()
            inputs.pop('csrf_token', None)
            if inputs['minimo_ordine'] == '':
                inputs['minimo_ordine'] = 0
            inputs['scadenza'] = str(da_form(inputs['scadenza']) + timedelta(hours=22))
            inputs['consegna'] = str(da_form(inputs['consegna']) + timedelta(hours=19))
            dbi.execute(
                """
                INSERT INTO dettagli_ordini {column_names}
                VALUES ({placeholders})
            """.format(
                    column_names=str(tuple(cn for cn in inputs)).replace('\'', ''),
                    placeholders=','.join('%s' for _ in range(len(inputs))),
                ),
                tuple(inputs.values()),
            )
            # Lo attivo, in quanto non sono sicuro lo fosse stato
            dbi.execute(
                'UPDATE produttori SET attivo = TRUE WHERE id = %s',
                (request.form['id_produttore'],),
            )
            return redirect(url_for('ordini.list_ordini'))

        flash(error['error_msg'], 'warning')

    # Seleziono solo i produttori che non hanno un ordine già aperto
    dbi.execute("""
            SELECT id, nome FROM produttori
            WHERE id NOT IN (SELECT id_produttore FROM dettagli_ordini)
            ORDER BY nome
                """)
    produttori = dbi.fetchall()
    if 'referente' in g.ruoli:
        produttori = list(filter(lambda p: p[0] in g.referenze, produttori))

    return render_template('ordini/create.html', produttori=produttori)


@bp.route('/update/<int:id_produttore>', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def update(id_produttore):
    """Aggiorno un ordine solo se ho i permessi per farlo"""

    if not is_mod_or_ref_of(id_produttore):
        return redirect(url_for('produttori.list_produttori'))

    get_db().execute(
        """
        SELECT scadenza, consegna, minimo_ordine, nota
        FROM dettagli_ordini
        WHERE id_produttore = %s
    """,
        [id_produttore],
    )
    dettaglio = get_db().fetchone()

    if request.method == 'POST':
        error = check_inputs_dettagli_ordine(request.form)

        try:
            scadenza = da_form(request.form['scadenza']) + timedelta(hours=22)
            consegna = da_form(request.form['consegna']) + timedelta(hours=19)

            if 'scadenza' in request.form and dettaglio['scadenza'] != scadenza:
                if adesso() > scadenza:
                    error = {
                        'error_msg': 'Non è consentito impostare scadenza nel passato'
                    }
            if 'consegna' in request.form and dettaglio['consegna'] != consegna:
                if adesso() > consegna:
                    error = {
                        'error_msg': 'Non è consentito impostare consegna nel passato'
                    }
        except ValueError:
            error = {'error_msg': u'Formato data non conforme'}

        if not error:
            inputs = request.form.copy()
            inputs.pop('csrf_token', None)
            if 'minimo_ordine' in inputs and inputs['minimo_ordine'] == '':
                inputs['minimo_ordine'] = 0
            if 'scadenza' in request.form:
                inputs['scadenza'] = str(scadenza)
            if 'consegna' in request.form:
                inputs['consegna'] = str(consegna)
            get_db().execute(
                """
                UPDATE dettagli_ordini SET {column_names} = ({placeholders})
                WHERE id_produttore = %s
            """.format(
                    column_names=str(tuple(cn for cn in inputs)).replace('\'', ''),
                    placeholders=','.join('%s' for _ in range(len(inputs))),
                ),
                tuple(inputs.values()) + (id_produttore,),
            )

            return redirect(url_for('ordini.list_ordini'))

        flash(error['error_msg'], 'warning')

    if dettaglio is None:  # Non vi sono ordini aperti
        # preparo la struttura per jinja, che accede alle keys
        dettaglio = {'scadenza': '', 'consegna': '', 'minimo_ordine': '', 'nota': ''}

    return render_template(
        'ordini/update.html',
        produttore=get_produttore(id_produttore),
        dettaglio=dettaglio,
        today=adesso(),
    )


@bp.route('/close/<int:id_produttore>', methods=['POST'])
@login_required
@is_ruolo(['moderatore', 'referente'])
def close(id_produttore):
    """Chiudo un ordine mantiene tutti gli ordini fatti dagli utenti"""

    dbi = get_db()

    # Per chiudere un ordine mi basta segnare la data di scadenza a ieri
    if 'conferma' in request.form:
        # Controlla se raggiunto minimo_ordine
        dbi.execute(
            """
                SELECT minimo_ordine FROM dettagli_ordini
                WHERE id_produttore = %s
                """,
            [id_produttore],
        )
        dettaglio_ordine = dbi.fetchone()
        if float(dettaglio_ordine['minimo_ordine']) < sum(
            get_spesa_totale_utenti(id_produttore).values()
        ):
            dbi.execute(
                """ UPDATE dettagli_ordini
                SET scadenza = CURRENT_TIMESTAMP(2) - interval '1 day'
                WHERE id_produttore = %s
            """,
                [id_produttore],
            )
        else:
            _delete(id_produttore)

        flash('Chiusura Ordine avvenuta con successo', 'success')
        return redirect(url_for('ordini.list_ordini'))

    if 'pre-conferma' in request.form:
        flash(
            'Sicuro di voler chiudere l\' ordine? I gasisti non potranno più'
            ' effettuare ordini e se non si è raggiunto'
            ' il minimo d\'ordine, tutti gli ordini andranno persi.',
            'warning',
        )
        return render_template(
            'ordini/update.html',
            produttore=get_produttore(id_produttore),
            dettaglio=_get_dettaglio(id_produttore),
            sicuro_close=True,
            today=adesso(),
        )

    return render_template(
        'ordini/update.html',
        produttore=get_produttore(id_produttore),
        dettaglio=_get_dettaglio(id_produttore),
        sicuro_close=False,
        today=adesso(),
    )


@bp.route('/delete/<int:id_produttore>', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def delete(id_produttore):
    """Cancella un ordine, compreso tutti gli ordini fatti dagli utenti"""
    if 'pre-conferma' in request.form:
        flash(
            'Sicuro di voler annullare e cancellare TUTTI gli ordini? Non'
            ' si torna più indietro se si conferma nuovamente.',
            'warning',
        )

        return render_template(
            'ordini/update.html',
            produttore=get_produttore(id_produttore),
            dettaglio=_get_dettaglio(id_produttore),
            sicuro=True,
            today=adesso(),
        )

    if 'conferma' in request.form:
        _delete(id_produttore)

    flash('Cancellazione Ordine avvenuta con successo', 'success')
    return redirect(url_for('produttori.list_produttori'))


@bp.route('/rettifica/<int:id_produttore>', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def rettifica_ordine(id_produttore):
    """Gestione Rettifiche per ordine"""
    dbi = get_db()
    dbi.execute("""
        SELECT id_utente, username, nome, cognome,
                SUM(prezzo*colli_richiesti) as totale_utente
        FROM ordine_in_corso_{0} INNER JOIN listino_{0}
                ON listino_{0}.id = id_prodotto
            INNER JOIN utenti ON utenti.id = id_utente
        GROUP BY id_utente, username, nome, cognome
        ORDER BY nome, cognome, username
        """.format(id_produttore))

    ordini = dbi.fetchall()
    minimo_ordine = get_minimo_ordine(id_produttore)
    sicuro = False

    if request.method == 'POST':
        extras = []

        if not check_inputs_rettifiche(request.form):

            extras = [
                {
                    'id_utente': request.form.getlist('extra_id_utente')[i],
                    'utente': request.form.getlist('extra_utente')[i],
                    'importo': float(request.form.getlist('extra_importo')[i]),
                    'descrizione': request.form.getlist('extra_descrizione')[i],
                }
                for i in range(len(request.form.getlist('extra_utente')))
            ]

            if request.form.get('rimuovi'):
                extras = list(
                    filter(
                        lambda e: e['id_utente'] != str(request.form.get('rimuovi')),
                        extras,
                    )
                )

            id_utente = request.form.get('per_id_utente')
            # Se sto aggiungendo un ordine extra
            if id_utente:
                id_utenti_extra = dict(
                    (e['id_utente'], i) for i, e in enumerate(extras)
                )
                if id_utente in id_utenti_extra.keys():
                    extras[id_utenti_extra[id_utente]]['importo'] += float(
                        request.form.get('importo')
                    )
                    extras[id_utenti_extra[id_utente]][
                        'descrizione'
                    ] += ' ' + request.form.get('descrizione')
                else:
                    utente = get_utente_by_id(id_utente)
                    utente = ' '.join(
                        [
                            utente['nome'],
                            utente['cognome'],
                            '(',
                            utente['username'],
                            ')',
                        ]
                    )
                    extras.append(
                        {
                            'id_utente': id_utente,
                            'utente': utente,
                            'importo': float(request.form.get('importo')),
                            'descrizione': request.form.get('descrizione'),
                        }
                    )

            nuovi_totali = [
                (
                    float(rettifica)
                    if rettifica and float(rettifica) > 0
                    else float(ordini[i]['totale_utente'])
                )
                for (i, rettifica) in enumerate(
                    request.form.getlist('importo_rettifica')
                )
            ]

            motivazioni = request.form.getlist('motivazione')
            if any(v <= 0 for v in nuovi_totali):
                flash(
                    """
                 Tra i totali effettivi vi è almeno un ordine con valore <= 0.
                 Non verranno aggiunti ai movimenti proseguendo!""",
                    'warning',
                )

            if 'pre-conferma' in request.form:
                flash(
                    'Sicuro di voler confermare i totali? Ricontrollali, non'
                    ' si torna più indietro se si conferma nuovamente.',
                    'warning',
                )
                sicuro = True

            if 'conferma' in request.form:
                # Scrivo solo i movimenti che hanno effettivamente una spesa,
                # importi 0 o negativi non vengono calcolati
                nuovi_totali = [nt for nt in nuovi_totali if nt > 0]

                # Solo se vi sono stati ordini, inserisco movimenti
                if nuovi_totali:
                    dbi.execute(
                        """
                        SELECT date(consegna) as data
                        FROM dettagli_ordini
                        WHERE id_produttore = %s""",
                        [id_produttore],
                    )
                    consegna = dbi.fetchone()['data']

                    # Aggiungo movimenti in cassa
                    for i, importo in enumerate(nuovi_totali):
                        _inserisci_rettifica(
                            request.form.getlist('id_utente')[i],
                            id_produttore,
                            importo,
                            motivazioni[i],
                            consegna,
                        )
                    for extra in extras:
                        _inserisci_rettifica(
                            extra['id_utente'],
                            id_produttore,
                            extra['importo'],
                            extra['descrizione'],
                            consegna,
                        )
                    dbi.execute(
                        """
                        INSERT INTO pagamenti_ordini (id_produttore, consegna)
                        VALUES (%s, %s)
                        """,
                        (id_produttore, consegna),
                    )

                _delete(id_produttore)
                flash('Rettifiche Ordine avvenute con successo, Ordine \
                        Completato', 'success')
                return redirect(
                    url_for('stampa.storico_tiny', id_produttore=id_produttore)
                )

            return render_template(
                'ordini/rettifica.html',
                extras=extras,
                importi_rettifica=request.form.getlist('importo_rettifica'),
                minimo_ordine=minimo_ordine,
                motivazioni=motivazioni or [],
                nuovi_totali=nuovi_totali,
                ordini=ordini,
                produttore=get_produttore(id_produttore),
                totale_ordine=sum([o['totale_utente'] for o in ordini]),
                sicuro=sicuro,
                utenti=get_utenti(vincolo=("attivo", True)),
            )

        flash(check_inputs_rettifiche(request.form)['error_msg'], 'warning')

    return render_template(
        'ordini/rettifica.html',
        minimo_ordine=minimo_ordine,
        ordini=ordini,
        produttore=get_produttore(id_produttore),
        totale_ordine=sum([o['totale_utente'] for o in ordini]),
        sicuro=sicuro,
        utenti=filter(
            lambda u: u['id'] not in set(o['id_utente'] for o in ordini),
            get_utenti(vincolo=("attivo", True)),
        ),
    )


@bp.route('/rettifica/<int:id_produttore>/rimuovi/<int:id_utente>')
@login_required
@is_ruolo(['moderatore', 'referente'])
def rimuovi_singolo_ordine(id_produttore, id_utente):
    """Rimuove un intero ordine in fase di rettifica"""
    get_db().execute(
        """
        DELETE FROM ordine_in_corso_{0} WHERE id_utente = %s
        """.format(id_produttore),
        [id_utente],
    )
    return redirect(url_for('ordini.rettifica_ordine', id_produttore=id_produttore))
