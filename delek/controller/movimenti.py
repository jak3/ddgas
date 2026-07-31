""" Gestione dei Movimenti di ogni produttore """
import csv
import json
from datetime import datetime
from io import StringIO, BytesIO

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, send_file
)

from psycopg2.extensions import AsIs

from werkzeug.datastructures import MultiDict

from delek.model.checks import (
    check_inputs_movimento, check_valid_date, check_aggiusta_ordine_chiuso
)

from delek.controller.produttori import get_storico_ordini
from delek.controller.auth import (
    login_required, is_ruolo, get_utenti, get_utente_by_id
)
from delek.controller.db import get_db, atomic

bp = Blueprint('movimenti', __name__, url_prefix='/movimenti')


@bp.app_template_filter('movimento')
def movimento_filter(movimento: dict):
    """ Rappresentazione testuale di un movimento """
    return '\\n'.join(filter(None, [
        movimento['effettuato_il'].strftime('%d / %m / %Y'),
        ' '.join(filter(None, [
            movimento.get('nome', '') or '',
            movimento.get('cognome', '') or '',
            ''.join([' (', movimento['username'], ')'])
            if movimento['username'] else 'Cassa'])),
        str(movimento['importo']),
        movimento['tipologia_movimento'],
        movimento['descrizione'],
        ' '.join([' (', movimento['produttore'], ')']) if
        movimento.get('produttore', '') or ''
        else ''
    ]))


def is_in_args_or_form(what):
    """ Return Boolean, True if :what is in request args or form """
    return any(what in where for where in [request.args, request.form.keys()]
               if where)


def get_totale(id_utente=''):
    """ Ritorna il totale
            in cassa (considerando i saldi utente): get_totale()
            nel conto di un utente                : get_totale(1)
        sommando tra loro tutti i movimenti """
    # La tipologia '6' è un aggiustamento che viene fatto utilizzando come
    # 'per_id_utente' l'id di un produttore e non un utente.
    get_db().execute("""
            SELECT SUM(importo) as totale FROM movimenti
            WHERE %s = %s and tipologia != 6;""",
                     (AsIs('per_id_utente'), id_utente)
                     if id_utente else (1, 1))

    row = get_db().fetchone()
    return row['totale'] if row[0] else 0


def get_totale_utente(id_utente):  # alias get_totale
    """ Ritorna il totale nel conto di un utente,
        sommando tra loro tutti i movimenti presenti. """
    return get_totale(id_utente)


def get_totale_cassa():
    """ Ritorna il totale in cassa (senza considerare i saldi utente) """
    get_db().execute("""
            SELECT SUM(importo) as totale FROM movimenti
            WHERE per_id_utente IS NULL
        """)

    row = get_db().fetchone()
    return row['totale'] if row[0] else 0


def get_totale_tutti_ordini_in_corso():
    """ Ritorna il totale complessivo di tutti gli ordini in corso
        utilizzando una query SQL ottimizzata """
    dbi = get_db()

    # Ottieni tutti i produttori con ordini aperti
    dbi.execute('SELECT id_produttore FROM dettagli_ordini')
    id_produttori = [row['id_produttore'] for row in dbi.fetchall()]

    if not id_produttori:
        return 0

    totale_complessivo = 0

    for id_produttore in id_produttori:
        dbi.execute(
            """
            SELECT COALESCE(SUM(colli_richiesti * prezzo), 0) as totale
            FROM ordine_in_corso_{0}
            INNER JOIN listino_{0} ON listino_{0}.id = id_prodotto
            """.format(id_produttore)
        )
        row = dbi.fetchone()
        totale_complessivo += float(row['totale']) if row['totale'] else 0

    return totale_complessivo


def insert_movimento(movimento: dict):
    """ Wrap per inserire un movimento """
    cp_movimento = movimento.copy()
    for campo_non_colonna in ('verso_id', 'csrf_token'):
        cp_movimento.pop(campo_non_colonna, None)
    get_db().execute("""
            INSERT INTO movimenti {column_names} VALUES ({placeholders})
        """.format(column_names=str(tuple(cn for cn in cp_movimento)
                                    ).replace('\'', ''),
                   placeholders=','.join('%s'
                                         for _ in range(len(cp_movimento))
                                         )
                   ),
        tuple(cp_movimento.values())
    )


def get_tipologie_movimenti():
    """ Tipologie di Movimenti disponibili """
    get_db().execute('SELECT * from tipologie_movimenti')
    return get_db().fetchall()


def _handle(inputs):
    error = check_inputs_movimento(inputs)

    if not error:
        inputs = dict(inputs)

        saldo = (float(get_totale_utente(inputs['per_id_utente']))
                 if 'per_id_utente' in inputs.keys()
                 else float(get_totale_cassa()))

        tipologie = {v: k for k, v in dict(get_tipologie_movimenti()).items()}
        error_exceed = {'error_msg':
                        u'Non presenti abbastanza soldi nel portafoglio'}

        if int(inputs['tipologia']) == tipologie['rettifica']:
            # vi è abbastanza saldo nel portafoglio?
            if (float(inputs['importo']) > 0 and
               (saldo and saldo < -1 * float(inputs['importo']))):
                return error_exceed

        if (int(inputs['tipologia']) in
            [tipologie['versamento'],  # +valore
             tipologie['prelievo'],   # -valore
             tipologie['giroconto']   # -valore
             # In un giroconto, si hanno due transazioni:
             # 1. (prelevo da) per_id_utente, -valore
             # 2. (verso a) per_id_utente, +valore
             ]):

            if float(inputs['importo']) < 0:
                return {'error_msg': u'Importo negativo non valido'}

            if int(inputs['tipologia']) != tipologie['versamento']:  # -valore
                # vi è abbastanza saldo nel portafoglio?
                if saldo < float(inputs['importo']):
                    return error_exceed
                inputs = inputs | {'importo': -1 * float(inputs['importo'])}

            if int(inputs['tipologia']) == tipologie['giroconto']:
                destinatario = get_utente_by_id(inputs['verso_id'])
                inputs |= {'descrizione': inputs['descrizione'] +
                           ' (versato a {username})'.format(
                    username=destinatario['username']
                )
                }

        if (int(inputs['tipologia']) == tipologie['giroconto'] and
                inputs['per_id_utente'] == inputs['verso_id']):
            return {'error_msg':
                    u'Un giroconto necessita di due utenti diversi'
                    }

        with atomic():
            insert_movimento(inputs)

            if int(inputs['tipologia']) == tipologie['giroconto']:
                # In (2) vedi sopra
                insert_movimento(inputs | {
                    'per_id_utente': inputs['verso_id'],
                    # Devo fare nuovamente -1* in quanto avevo cambiato segno
                    'importo': -1 * float(inputs['importo'])
                })

        return {}

    return error


@bp.route('/', methods=['GET', 'POST'])
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def handle():
    """ Pagina di gestione movimenti.
        GET lista dei movimenti
        POST creazione movimento, che può essere:
            - Versamento (di un utente verso `movimenti` +)
            - Prelievo   (di un utente da `movimenti` -)
            - Giroconto  (di un utente verso un altro utente)
            - Aggiustamento (si aggiusta un ordine già rettificato)
            - Spese CC (spese del Conto Corrente di tutti i gasisti)
            - Spese Varie
    """
    error = {}

    if request.method == 'POST':
        inputs = dict(request.form)
        if '- - -' in request.form['per_id_utente']:
            inputs.pop('per_id_utente')
        if not request.form['effettuato_il']:
            inputs.pop('effettuato_il')

        error = _handle(inputs)

        if not error:
            flash('Creazione del movimento avvenuta con successo', 'success')
        else:
            flash(error['error_msg'], 'warning')

    return render_template('movimenti/create.html',
                           utenti=get_utenti(),
                           totale=get_totale() if not error else None,
                           totale_ordini_in_corso=get_totale_tutti_ordini_in_corso(),
                           totale_cassa_aggiustamenti=get_totale_cassa(),
                           tipologie=get_tipologie_movimenti())


@bp.route('/girocontoa', methods=['GET', 'POST'])
@login_required
def giroconto_utente():
    """ Permette a un utente senza ruolo di tesoriere o moderatore di
        effettuare un Giroconto ad un altro Gasista
    """
    if request.method == 'POST':
        inputs = dict(request.form) | {
            'tipologia': 3,
            'per_id_utente': g.user['id']}

        # Precondizione da controllare prima di leggere verso_id: senza,
        # una select senza scelta esplicita punterebbe silenziosamente al
        # primo utente della lista, inviando credito alla persona sbagliata.
        if '- - -' in inputs.get('verso_id', '- - -'):
            error = {'error_msg':
                     "Selezionare l'utente verso cui effettuare il"
                     ' giroconto'}
        else:
            dauser = get_utente_by_id(inputs['per_id_utente'])['username']
            auser = get_utente_by_id(inputs['verso_id'])['username']
            inputs['descrizione'] = (
                f'[Giroconto da {dauser} verso {auser}] '
                + inputs['descrizione'])

            error = check_inputs_movimento(inputs)

            if not error and float(inputs['importo']) < 0:
                # Un importo negativo qui invertirebbe il verso del giroconto:
                # chi lo invia riceverebbe credito e il destinatario verrebbe
                # addebitato a sua insaputa.
                error = {'error_msg': 'Importo negativo non valido'}

            if not error:
                saldo = float(get_totale_utente(inputs['per_id_utente']))
                if saldo < float(inputs['importo']):
                    error = {'error_msg':
                             'Non presenti abbastanza soldi nel portafoglio.'
                             ' Vai alla voce Ricarica per accreditare con'
                             ' carta.'}

            if not error:
                with atomic():
                    # Negativo per chi esegue
                    insert_movimento(inputs | {
                        'importo': -1 * float(inputs['importo'])
                    })
                    # Positivo per chi riceve
                    insert_movimento(inputs | {
                        'per_id_utente': inputs['verso_id'],
                    })
                flash('Giroconto avvenuto con successo', 'success')

        if error:
            flash(error['error_msg'], 'warning')

    return render_template('movimenti/girocontoa.html',
                           utenti=get_utenti(),
                           totale=get_totale_utente(g.user['id']),
                           tipologie=get_tipologie_movimenti())


def _list_movimenti(query, id_utente=None, own_only=False):
    """ [ Mese (default), Trimestre, Per range di data ] """
    dbi = get_db()
    error = {}
    filtro = []
    movimenti = []

    if is_in_args_or_form('mese'):
        filtro += ['effettuato_il > date(\'now\') - \'1 month\'::interval']
    elif is_in_args_or_form('trimestre'):
        filtro += ['effettuato_il > date(\'now\') - \'3 month\'::interval']

    if request.method == 'POST':

        da_data = request.form['da_data'] if 'da_data' in request.form else ''
        a_data = request.form['a_data'] if 'a_data' in request.form else ''

        # NB: ogni controllo si accumula sui precedenti (error = error or
        # ...) invece di sovrascriverli: un controllo successivo valido non
        # deve poter cancellare l'esito di uno precedente non valido, pena
        # l'esecuzione della query con un filtro non validato.
        if da_data:
            error = error or check_valid_date(da_data)
            filtro += ['effettuato_il > date(\'{0}\')'.format(da_data)]
        if a_data:
            error = error or check_valid_date(a_data)
            filtro += ['effettuato_il < date(\'{0}\')'.format(a_data)]

        if (not own_only and 'id_utente' in request.form and
                '- - -' not in request.form['id_utente']):
            error = error or check_inputs_movimento(MultiDict({
                'per_id_utente': request.form['id_utente']
            }))
            filtro += ['utenti.id = ' + request.form['id_utente']]
            id_utente = int(request.form['id_utente'])

        if ('tipologia' in request.form and
                '- - -' not in request.form['tipologia']):
            error = error or ({} if request.form['tipologia'].isdigit() else
                              {'error_msg': 'Tipologia non conforme'})
            filtro += ['tipologie_movimenti.id = ' + request.form['tipologia']]

    query_params = ((id_utente, AsIs(' AND '.join([''] + filtro))) if id_utente
                    else
                    [AsIs(' AND '.join([
                        "tipologie_movimenti.nome != 'acquisto'"] + filtro))
                     ])

    if not error:
        dbi.execute(query, query_params)
        movimenti = dbi.fetchall()
    else:
        flash(error['error_msg'], 'warning')

    return movimenti


@bp.route('/list', methods=['GET', 'POST'])
@login_required
def list_movimenti():
    """ Pagina di visualizzazione movimenti per g.user['id']
        Un movimento ha data, importo, tipologia (se trattasi di acquisto, tra
        parentesi segue il nome del produttore).
    """
    id_utente = g.user['id']

    query = """
            SELECT movimenti.id, importo, descrizione, effettuato_il
            FROM movimenti INNER JOIN tipologie_movimenti
                             ON tipologie_movimenti.id = movimenti.tipologia
            WHERE per_id_utente = %s %s
            ORDER BY effettuato_il DESC
            """

    movimenti = _list_movimenti(query, id_utente=id_utente, own_only=True)

    return render_template('movimenti/list.html',
                           totale=get_totale(id_utente=id_utente),
                           movimenti=movimenti)


@bp.route('/list/all', methods=['GET', 'POST'])
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def list_movimenti_all():
    """ Pagina di visualizzazione dei movimenti di tutti gli utenti:
        [ Mese (default), Trimestre, Per range di data ] """
    dbi = get_db()
    totale_utente = None
    format_string = '%s'

    if ('id_utente' in request.form and
            '- - -' not in request.form['id_utente']):
        dbi.execute('SELECT sum(importo) as totale'
                    ' FROM movimenti WHERE per_id_utente = %s',
                    [request.form['id_utente']])
        row = dbi.fetchone()
        format_string = 'per_id_utente = %s %s'
        if row['totale']:
            totale_utente = float(row['totale'])

    query = """
            SELECT movimenti.id, username, utenti.nome, utenti.cognome,
                   tipologie_movimenti.nome as tipologia_movimento, importo,
                   descrizione, effettuato_il
            FROM movimenti LEFT OUTER JOIN utenti
                             ON utenti.id = movimenti.per_id_utente
                           INNER JOIN tipologie_movimenti
                             ON tipologie_movimenti.id = movimenti.tipologia
            WHERE {0}
            ORDER BY effettuato_il DESC
            """.format(format_string)

    dbi.execute("SELECT * FROM tipologie_movimenti WHERE nome != 'acquisto'")
    tipologie_movimenti = dbi.fetchall()

    return render_template('movimenti/list_all.html',
                           utenti=get_utenti(),
                           tipologie_movimenti=tipologie_movimenti,
                           totale=get_totale(),
                           totale_ordini_in_corso=get_totale_tutti_ordini_in_corso(),
                           totale_cassa_aggiustamenti=get_totale_cassa(),
                           totale_utente=totale_utente,
                           movimenti=_list_movimenti(query))


def _totali_conti_utenti():
    get_db().execute('''SELECT id, username, attivo FROM utenti
                        ORDER BY attivo, username
                     ''')
    utenti = get_db().fetchall()
    return [{'username': utente['username'],
             'totale': float(get_totale(utente['id'])),
             'attivo': utente['attivo']} for utente in utenti]


@bp.route('/totali', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def totali_conti_utenti():
    """ Stampa un elenco dei totali nei conti di ogni utente """
    return render_template('movimenti/totali_conti_utenti.html',
                           totali=_totali_conti_utenti())


@bp.route('/esporta')
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def esporta():
    """ Esporta elenco dei totali in cassa """
    content = StringIO()
    list_dict_totali = _totali_conti_utenti()
    writer = csv.DictWriter(content, fieldnames=list_dict_totali[0].keys())
    writer.writeheader()
    writer.writerows(list_dict_totali)
    mem = BytesIO()
    mem.write(content.getvalue().encode())
    mem.seek(0)
    content.close()
    return send_file(mem,
                     as_attachment=True,
                     download_name='totali_conti_utenti.csv',
                     mimetype='text/csv'
                     )


@bp.route('/rettifica', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def rettifica_utente():
    """ Nel caso ci sia la necessita di effettuare una rettifica a un singolo
    utente, per esempio se vi sono stati errori nella chiusura.
    AL MOMENTO NON UTILIZZATO, da controllare che non ci siano degli errori
    in quanto non associa un ordine specifico alla rettifica, quindi cosa si
    rettifica? """

    if request.method == 'POST':

        error = _handle(dict(request.form) | {
            'verso_id': request.form['per_id_utente'],
            'gestore': g.user['id'],
            'tipologia': 5}
        )

        if not error:
            flash('Rettifica avvenuta con successo', 'success')
        else:
            flash(error['error_msg'], 'warning')

    return render_template('movimenti/rettifica.html',
                           utenti=get_utenti())


@bp.route('/aggiusta', methods=['POST'])
@login_required
@is_ruolo(['moderatore', 'referente'])
def aggiusta_ordine_chiuso():
    """ Nel caso ci sia la necessità di aggiustare il totale di un ordine
        chiuso
    """
    dbi = get_db()
    error = check_aggiusta_ordine_chiuso(request.form)

    if not error:
        id_produttore = request.form['id_produttore']
        # tipologia 6 = aggiustamento
        # Se prima era minore devo togliere soldi dalla cassa
        # 30 40 (-10 in cassa)
        # altrimenti devo aggiungere
        # 40 30 (10 rimetto 10 in cassa)
        # se uguali, lascio il mondo come sta.
        nuovo_totale = (float(sum([o['importo'] for o in
                                   get_storico_ordini(id_produttore,
                                   datetime.fromisoformat(request.form['data'])
                                                      )]
                                  )) - float(request.form['nuovo_totale']))
        if not nuovo_totale:
            flash('Non serve aggiustare se i totali coincidono', 'warning')
            return redirect(url_for('produttori.list_produttori'))

        dbi.execute("""
        INSERT INTO movimenti
            (gestore, tipologia, importo, descrizione)
                VALUES (%s, %s, %s, %s) RETURNING id
        """, (g.user['id'], 6, nuovo_totale, request.form['descrizione']))

        id_movimento = dbi.fetchone()['id']
        dbi.execute("""
        INSERT INTO storico_ordini
        (id_produttore, id_utente, importo, consegna, dettaglio, id_movimento)
        VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_produttore, g.user['id'], nuovo_totale, request.form['data'],
              json.dumps(request.form['descrizione']), id_movimento))

        flash('Nuovo Totale Aggiornato. Differenza sommata alla cassa',
              'success')
        return redirect(url_for('produttori.list_produttori',
                                id_produttore=id_produttore))

    flash(error['error_msg'], 'warning')

    return redirect(url_for('produttori.list_produttori'))


@bp.route('/delete/<int:id_movimento>', methods=('POST',))
@login_required
@is_ruolo(['tesoriere'])
def delete(id_movimento):
    """ Cancella un movimento """
    get_db().execute('DELETE FROM movimenti WHERE id = %s', [id_movimento])
    flash('Movimento cancellato con successo', 'success')
    return redirect(url_for('movimenti.list_movimenti_all'))
