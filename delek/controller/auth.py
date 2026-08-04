"""Autenticazione Utenti"""

from io import StringIO, BytesIO
from functools import wraps
from datetime import datetime, date, timedelta
import jwt
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    Response,
    current_app,
    send_file,
)

from psycopg2.extensions import AsIs

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import abort

from delek.model.checks import (
    check_inputs_utente,
    check_inputs_isid,
    check_inputs_quota,
    check_inputs_smemo,
)

from delek.controller.db import get_db, atomic
from delek.controller.tempo import adesso

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.app_template_filter('utente')
def utente_filter(utente: dict):
    """Rappresentazione testuale di un utente"""
    return ' '.join(
        filter(
            None,
            [
                utente.get('nome', '') or '',
                utente.get('cognome', '') or '',
                ' (',
                utente['username'],
                ')',
                '· ' + utente.get('cf').upper() if utente.get('cf', '') else '',
                '· ' + utente.get('email') if utente.get('email', '') else '',
                '· ' + utente.get('telefono') if utente.get('telefono', '') else '',
            ],
        )
    )


def login_required(view):
    """Decorator per operazioni che richiedono il login"""

    @wraps(view)
    def wrap_login(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrap_login


def is_presidiante():
    """Controllo se l'utente che richiede i dettagli è un presidiante"""
    get_db().execute("""
    SELECT id_utente FROM presidi
    WHERE date_trunc('day', giorno) = date_trunc('day', now())
    """)
    presidianti = [row['id_utente'] for row in get_db().fetchall()]
    return g.user['id'] in presidianti


def is_ruolo(what: list):
    """Decorator per check credenziali"""

    def is_ruolo_inner(view):
        @wraps(view)
        def _(*args, **kwargs):
            if 'presidiante' in what and is_presidiante():
                return view(*args, **kwargs)
            if len(set(what).intersection(set(g.ruoli))) <= 0:
                abort(403)
            if (
                'moderatore' not in what
                and 'referente' in what
                and 'id_produttore' in kwargs
                and kwargs['id_produttore'] not in g.referenze
            ):
                abort(403)
            return view(*args, **kwargs)

        return _

    return is_ruolo_inner


def is_mod_or_ref_of(id_produttore):
    """Check se è moderatore o referente del produttore id_produttore"""
    is_moderatore = 'moderatore' in g.ruoli
    is_referente = 'referente' in g.ruoli
    of_produttore = id_produttore in g.referenze

    return is_moderatore or (is_referente and of_produttore)


def attiva_utente(id_utente):
    """Attiva un utente nella tabella utenti"""
    dbi = get_db()
    dbi.execute('UPDATE utenti SET attivo = TRUE WHERE id = %s', (id_utente,))


def get_utente(vincolo=(1, 1)):
    """:vincolo arg utilizzato in clausola WHERE"""
    vincolo = (AsIs(vincolo[0]) if type(vincolo[0]) is str else vincolo[0], vincolo[1])
    get_db().execute('SELECT * FROM utenti WHERE %s = %s', vincolo)
    return get_db().fetchone()


def get_utente_by_username(username):
    """wrap get_utente_with_where"""
    return get_utente((AsIs('username'), username))


def get_utente_by_id(id_utente):
    """wrap get_utente_with_where"""
    return get_utente((AsIs('id'), id_utente))


def get_utenti(vincolo=(1, 1)):
    """Lista di tutti gli utenti"""
    vincolo = (AsIs(vincolo[0]) if type(vincolo[0]) is str else vincolo[0], vincolo[1])
    get_db().execute(
        """
           SELECT id, username, nome, cognome, email, telefono, attivo
           FROM utenti WHERE %s = %s ORDER BY nome, cognome
        """,
        vincolo,
    )
    return get_db().fetchall()


def get_nuovi_utenti():
    """Lista dei nuovi utenti, che richiedono l'attivazione"""
    get_db().execute("""
            SELECT id_utente, username, email, telefono, nome, cognome,
                    data_iscrizione
            FROM nuovi_utenti INNER JOIN utenti
             ON nuovi_utenti.id_utente = utenti.id
            ORDER BY data_iscrizione
            """)
    return get_db().fetchall()


@bp.route('/esporta/soci')
@login_required
@is_ruolo(['moderatore', 'segretario'])
def esporta_soci():
    """Esporta elenco degli utenti per il libro soci associazione"""
    content = StringIO()
    dbi = get_db()
    dbi.execute(
        'SELECT data_inizio FROM campagne_tesseramenti'
        ' ORDER BY data_inizio DESC LIMIT 1'
    )
    # importo < 0 serve per togliere il fondo cassa (FCA) che riceve
    # i soldi degli utenti
    query = """COPY (
    SELECT username, nome, cognome, cf, email, telefono
    FROM movimenti INNER JOIN utenti
        ON movimenti.per_id_utente = utenti.id
    WHERE tipologia = 3 AND descrizione LIKE 'Tesseramento%%' AND
        effettuato_il > to_date('{0}', 'YYYY-MM-DD') AND
        effettuato_il < to_date('{0}', 'YYYY-MM-DD') + interval '365 days' AND
        importo < 0
    ORDER BY nome, cognome) TO STDOUT WITH CSV HEADER
    """.format(dbi.fetchone()['data_inizio'].isoformat())

    dbi.copy_expert(query, content)
    mem = BytesIO()
    mem.write(content.getvalue().encode())
    mem.seek(0)
    content.close()
    return send_file(
        mem, as_attachment=True, download_name='elenco-soci.csv', mimetype='text/csv'
    )


@bp.route('/esporta/inattivi')
@login_required
@is_ruolo(['moderatore', 'segretario'])
def esporta_inattivi():
    """Esporta elenco degli utenti inattivi"""
    content = StringIO()
    dbi = get_db()
    query = """COPY (
    SELECT username, nome, cognome, cf, email, telefono
    FROM utenti WHERE attivo = false) TO STDOUT WITH CSV HEADER
    """

    dbi.copy_expert(query, content)
    mem = BytesIO()
    mem.write(content.getvalue().encode())
    mem.seek(0)
    content.close()
    return send_file(
        mem,
        as_attachment=True,
        download_name='elenco-inattivi.csv',
        mimetype='text/csv',
    )


@bp.route('/register', methods=('GET', 'POST'))
def register():
    """Registrazione Utente"""
    if request.method == 'POST':
        error = check_inputs_utente(request.form)

        if not error:
            if get_utente_by_username(request.form['username']) is not None:
                error = {
                    'error_msg': ' '.join(
                        ['Utente', request.form['username'], 'già registrato.']
                    )
                }
            else:
                dbi = get_db()
                dbi.execute(
                    """
                    INSERT INTO utenti (username, password, email,
                                        nome, cognome, cf, telefono)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """,
                    (
                        request.form['username'],
                        generate_password_hash(request.form['password']),
                        request.form['email'],
                        request.form['nome'],
                        request.form['cognome'],
                        request.form['cf'].upper(),
                        request.form['telefono'],
                    ),
                )
                dbi.execute(
                    'INSERT INTO nuovi_utenti (id_utente) VALUES (%s)',
                    (dbi.fetchone()['id'],),
                )
                return render_template(
                    'auth/attivazione.html', username=request.form['username']
                )

        flash(error['error_msg'], 'warning')

    return render_template('auth/register.html')


@bp.route('/smemo', methods=('GET', 'POST'))
def smemo():
    """Genera un JWT per convalidare la richiesta di reset della password, e
    lo invia all'utente per email"""
    if request.method == 'POST':
        dbi = get_db()
        error = check_inputs_smemo(request.form)
        if not error:
            username, email = request.form['username'], request.form['email']
            dbi.execute(
                'SELECT id FROM utenti WHERE username = %s AND email = %s',
                (username, email),
            )
            if dbi.fetchone():
                token = jwt.encode(
                    {"exp": datetime.now() + timedelta(hours=1), "username": username},
                    current_app.config['SECRET_KEY'],
                )
                reset_link = ''.join(
                    [request.host_url, url_for('auth.reset_password'), '?token=', token]
                )
                msg = Mail(
                    from_email=current_app.config['SENDGRID_FROM_EMAIL'],
                    to_emails=email,
                    subject='GasMa - Reset della password',
                    plain_text_content=''.join(
                        [
                            'Visita la seguente pagina per effettuare il',
                            ' reset della tua password ( ',
                            username,
                            ' ).\n',
                            reset_link,
                        ]
                    ),
                )
                SendGridAPIClient(current_app.config['SENDGRID_API_KEY']).send(msg)
                flash(
                    ' '.join(
                        [
                            'Richiesta ripristino password avvenuta con successo.',
                            'Visita il link presente nell\'email per cambiarla.',
                        ]
                    ),
                    'success',
                )
                return redirect(url_for('auth.login'))

            error = {'error_msg': 'Username ed Email non corrispondono'}

        flash(error['error_msg'], 'warning')

    return render_template('auth/smemo.html')


def is_tesserato(id_utente, giorni_esenzione=60):
    """Check if id_utente ha un movimento con descrizione = Tesseramento

    Args:
        id_utente: ID dell'utente da controllare
        giorni_esenzione: Numero di giorni prima della scadenza in cui non
                         richiedere il tesseramento (default: 60)
    """
    dbi = get_db()
    # Recupera solo campagne ancora valide (entro 365 giorni)
    dbi.execute("""
        SELECT data_inizio FROM campagne_tesseramenti
        WHERE data_inizio > CURRENT_DATE - interval '365 days'
        ORDER BY data_inizio DESC LIMIT 1
    """)
    campagna = dbi.fetchone()

    if campagna:
        from datetime import datetime, timedelta

        data_scadenza_campagna = campagna['data_inizio'] + timedelta(days=365)
        inizio_periodo_esenzione = data_scadenza_campagna - timedelta(
            days=giorni_esenzione
        )

        if adesso() >= inizio_periodo_esenzione and adesso() < data_scadenza_campagna:
            return True

        dbi.execute(
            """
        SELECT 1 FROM movimenti
        WHERE tipologia = 3 AND descrizione LIKE 'Tesseramento%%' AND
            per_id_utente = %(id)s AND
            effettuato_il > %(data)s AND
            effettuato_il < %(data)s + interval '365 days'
        """,
            {
                'id': id_utente,
                'data': date(
                    campagna['data_inizio'].year,
                    campagna['data_inizio'].month,
                    campagna['data_inizio'].day,
                ),
            },
        )
        result = dbi.fetchone()

        return bool(result)

    return True  # se non vi è una campagna, considero tesserato


def get_ultima_campagna_tesseramenti():
    """Ritorna l'ultima campagna di tesseramenti (data_inizio, quota)"""
    get_db().execute(
        'SELECT EXTRACT(YEAR FROM data_inizio) AS anno, quota'
        ' FROM campagne_tesseramenti'
        ' ORDER BY data_inizio DESC LIMIT 1'
    )
    return get_db().fetchone()


def is_produttore(id_utente):
    """Check if 'produttore' is in g.ruoli if g is not None
    (must be logged)"""
    get_db().execute(
        """ SELECT 1
        FROM arruolati INNER JOIN ruoli ON ruoli.id = arruolati.id_ruolo
        WHERE ruolo = %s AND id_utente = %s
        """,
        ('produttore', id_utente),
    )

    return bool(get_db().fetchone())


@bp.route('/login', methods=('GET', 'POST'))
def login():
    """Login Utente"""
    if g.user:
        return redirect(url_for('produttori.list_produttori'))

    if request.method == 'POST':
        user = get_utente_by_username(request.form['username'])

        if user is None or not check_password_hash(
            user['password'], request.form['password']
        ):
            flash('Username o password errati', 'warning')
        elif not is_tesserato(user['id']) and not is_produttore(user['id']):
            session.clear()
            session['pending_tesseramento'] = user['id']
            return render_template(
                'auth/effettua_tesseramento.html',
                campagna=get_ultima_campagna_tesseramenti(),
            )
        else:
            session.clear()
            session['id_utente'] = user['id']
            return redirect(url_for('ordini.list_ordini'))

    return render_template('auth/login.html')


@bp.before_app_request
def load_logged_in_user():
    """Gestione della Sessione Utente:
    g.user = DB Row rif. all'utente
    g.ruoli = [ 'moderatore', 'referente' ]
    ID dei produttori di cui si possiedono le referenze
    g.referenze = [ '1', '3', '2' ]"""
    user_id = session.get('id_utente')

    if user_id is None:
        g.user = None
    else:
        dbi = get_db()
        g.user = get_utente_by_id(user_id)
        dbi.execute(
            """
            SELECT ruolo
            FROM arruolati INNER JOIN ruoli ON ruoli.id = arruolati.id_ruolo
            WHERE arruolati.id_utente = %s""",
            (g.user['id'],),
        )
        ruoli = dbi.fetchall()
        # [ Row Obj1, Row Obj2] => ['moderatore', 'referente']
        g.ruoli = [row['ruolo'] for row in ruoli]
        dbi.execute(
            """
            SELECT id_produttore FROM referenze
            WHERE id_utente = %s""",
            (g.user['id'],),
        )
        produttori = dbi.fetchall()
        g.referenze = [row['id_produttore'] for row in produttori]


@bp.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('index'))


COLONNE_UTENTE_MODIFICABILI = (
    'username',
    'password',
    'email',
    'telefono',
    'nome',
    'cognome',
    'cf',
)


def _update_user(inputs: dict, id_utente):
    '''Aggiorna le informazioni utente'''

    if inputs.get('password'):  # se voglio cambiare password
        error = check_inputs_utente(inputs)
        inputs.update({'password': generate_password_hash(inputs.get('password'))})
    else:
        inputs.pop('password')
        error = check_inputs_utente(inputs)

    # Whitelist esplicita: 'id' è validato da check_inputs_utente (serve
    # altrove) ma non deve mai poter finire tra le colonne aggiornabili
    inputs = {k: v for k, v in inputs.items() if k in COLONNE_UTENTE_MODIFICABILI}

    if not error:
        get_db().execute(
            """
            UPDATE utenti SET {column_names} = ({placeholders})
            WHERE id = %s
            """.format(
                column_names=str(tuple(cn for cn in inputs)).replace('\'', ''),
                placeholders=','.join('%s' for _ in range(len(inputs))),
            ),
            tuple(v for v in inputs.values()) + (id_utente,),
        )

        flash('Informazioni Utente aggiornate con successo', 'success')
    else:
        flash(error['error_msg'], 'warning')


@bp.route('/info', methods=('GET', 'POST'))
@login_required
def info_utente():
    """Gestione Informazioni Utente, include cambio password"""
    if request.method == 'POST':
        _update_user(dict(request.form), g.user['id'])

    get_db().execute(
        'SELECT codice FROM codici_ente_terzo WHERE id_utente = %s', [g.user['id']]
    )
    row = get_db().fetchone()
    return render_template(
        'auth/info_utente.html', codice_ente_terzo=row['codice'] if row else ''
    )


@bp.route('/<int:id_utente>/toggle', methods=('POST',))
@login_required
@is_ruolo(['moderatore', 'referente'])
def toggle_attivo(id_utente):
    """Cambia stato all' utente"""
    get_db().execute(
        'UPDATE utenti SET attivo = NOT attivo WHERE id = %s', (id_utente,)
    )
    return redirect(url_for('auth.gestione_permessi', id_utente=id_utente))


@bp.route('/ruoli/<int:id_utente>', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore'])
def gestione_permessi(id_utente):
    """Gestione Ruoli/Permessi per un Utente"""
    dbi = get_db()

    dbi.execute(
        """ SELECT id, username, nome, cognome, email, telefono, attivo, cf
            FROM utenti WHERE id = %s
        """,
        (id_utente,),
    )

    utente = dbi.fetchone()
    if not utente:
        flash('Utente non trovato', 'warning')
        return redirect('auth.list_utenti')

    if request.method == 'POST':
        inputs = dict(request.form)
        if 'password' in inputs.keys():
            inputs.pop('password')

        error = (
            check_inputs_utente(inputs)
            if len(inputs.keys()) > 1
            # 'id_ruolo' o 'id_produttore'
            else check_inputs_isid({'id': list(inputs.values())[0]})
        )

        if not error:
            if 'id_ruolo' in request.form.keys():
                dbi.execute(
                    """
                    INSERT INTO arruolati (id_ruolo, id_utente) VALUES (%s, %s)
                    """,
                    (request.form.get('id_ruolo'), id_utente),
                )

                flash('Ruolo associato correttamente', 'success')
            elif 'id_produttore' in request.form.keys():
                dbi.execute(
                    """
                    INSERT INTO referenze (id_produttore, id_utente)
                        VALUES (%s, %s)
                    """,
                    (request.form.get('id_produttore'), id_utente),
                )

                flash('Referenze associata correttamente', 'success')
            else:
                _update_user(dict(request.form), id_utente)
        else:
            flash('Sono stati riscontrati errori nella gestione', 'warning')
            return redirect(url_for('auth.gestione_permessi', id_utente=id_utente))

    dbi.execute(
        """ SELECT DISTINCT id_ruolo, ruolo as nome
            FROM arruolati INNER JOIN ruoli ON arruolati.id_ruolo = ruoli.id
            WHERE id_utente = %s
        """,
        (id_utente,),
    )

    ruoli_utente = dbi.fetchall()

    dbi.execute(
        """ SELECT produttori.id as id_produttore, nome
            FROM referenze INNER JOIN produttori
                ON referenze.id_produttore = produttori.id
            WHERE id_utente = %s
        """,
        (id_utente,),
    )

    referenze = dbi.fetchall()

    dbi.execute('SELECT * FROM ruoli')
    ruoli = dbi.fetchall()

    dbi.execute('SELECT id, nome FROM produttori ORDER BY nome')
    produttori = dbi.fetchall()

    return render_template(
        'auth/gestione_permessi.html',
        utente=utente,
        ruoli=ruoli,
        ruoli_utente=ruoli_utente,
        referenze=referenze,
        produttori=produttori,
    )


@bp.route('/remove/role/<int:id_ruolo>/<int:id_utente>', methods=('POST',))
@login_required
@is_ruolo(['moderatore'])
def remove_role(id_ruolo, id_utente):
    """Rimuove un ruolo ad un utente, se si tratta di referete, rimuove tutte
    le referenze collegate"""
    dbi = get_db()
    dbi.execute(
        'DELETE FROM arruolati WHERE id_ruolo = %s and id_utente = %s',
        (id_ruolo, id_utente),
    )
    dbi.execute('DELETE FROM referenze WHERE id_utente = %s', (id_utente,))

    flash('Ruolo rimosso con successo', 'success')
    return redirect(url_for('auth.gestione_permessi', id_utente=id_utente))


@bp.route('/remove/reference/<int:id_produttore>/<int:id_utente>', methods=('POST',))
@login_required
@is_ruolo(['moderatore'])
def remove_reference(id_produttore, id_utente):
    """Rimuove una referenza ad un utente"""
    get_db().execute(
        'DELETE FROM referenze WHERE id_produttore = %s and id_utente = %s',
        (id_produttore, id_utente),
    )
    flash('Referenza rimossa con successo', 'success')
    return redirect(url_for('auth.gestione_permessi', id_utente=id_utente))


@bp.route('/accoglienza')
@login_required
def accoglienza():
    """Stampa gli Utenti e le loro informazioni"""
    return render_template('auth/accoglienza.html', nuovi=get_nuovi_utenti())


@bp.route('/list')
@login_required
def list_utenti():
    """Stampa gli Utenti e le loro informazioni"""
    return render_template('auth/list.html', utenti=get_utenti())


@bp.route('/gestisci', methods=('GET', 'POST'))
@login_required
def gestisci_nuovi():
    """Attiva o Rimuovi i nuovi utenti selezionati"""
    if request.method == 'POST':
        dbi = get_db()

        if 'allin' in request.form:
            for nuovo_utente in get_nuovi_utenti():
                attiva_utente(nuovo_utente.id_utente)

        if any(a in request.form for a in ['allin', 'deleteall']):
            dbi.execute('DELETE FROM nuovi_utenti')
        else:
            for id_nuovo_utente in request.form.getlist('checkbox'):
                if 'delete' not in request.form:
                    attiva_utente(id_nuovo_utente)
                dbi.execute(
                    'DELETE FROM nuovi_utenti WHERE id_utente = %s', (id_nuovo_utente,)
                )

    return redirect(url_for('auth.list_utenti'))


@bp.route('/reset', methods=('GET', 'POST'))
def reset_password():
    """Reset password"""

    token_encoded = request.args.get('token')
    if request.method == 'POST':
        new_password = request.form['password']

        if new_password == request.form['password-check']:
            try:
                token = jwt.decode(
                    token_encoded,
                    current_app.config['SECRET_KEY'],
                    algorithms=["HS256"],
                )

                get_db().execute(
                    'UPDATE utenti SET password = %s WHERE username = %s',
                    (generate_password_hash(new_password), token['username']),
                )
                if get_db().rowcount:
                    flash('Password cambiata con successo.', 'success')
                    return redirect(url_for('auth.login'))

                flash('Impossibile aggiornare la password.', 'warning')

            except jwt.ExpiredSignatureError:
                flash('Token scaduto, ripetere la procedura.', 'warning')
            except jwt.PyJWTError:
                flash(
                    'Link di ripristino non valido, ripetere la' ' procedura.',
                    'warning',
                )
        else:
            flash('La conferma della password non corrisponde.', 'warning')

    return render_template('auth/reset_password.html', token=token_encoded)


@bp.route('/ente_terzo')
@login_required
@is_ruolo(['moderatore', 'tesseramenti'])
def list_ente_terzo():
    """Visualizza tutti i codici delle tessere dell'ente terzo (es. ARCI),
    vedi associazione.regole.tessera_ente_terzo"""
    get_db().execute("""
        SELECT username, nome, cognome, email, telefono, codice
        FROM utenti INNER JOIN codici_ente_terzo
            ON utenti.id = id_utente
        ORDER BY codice
        """)
    return render_template('auth/ente_terzo.html', utenti=get_db().fetchall())


@bp.route('/ente_terzo/download')
@login_required
@is_ruolo(['moderatore', 'tesseramenti'])
def download_ente_terzo():
    """Scarica il csv contenente il numero della tessera dell'ente terzo e
    il nome"""
    get_db().execute("""
        SELECT username, nome, cognome, codice
        FROM utenti INNER JOIN codici_ente_terzo ON utenti.id = id_utente
        """)
    csv_out = get_db().fetchall()
    csv_out = 'cognome,nome,username,codice\n' + '\n'.join(
        [
            ','.join([u['cognome'], u['nome'], u['username'], u['codice']])
            for u in csv_out
        ]
    )
    return Response(
        csv_out,
        mimetype="text/csv",
        headers={
            "Content-disposition": "attachment; filename=tesserati_ente_terzo.csv"
        },
    )


@bp.route('/tesseramenti', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'tesseramenti'])
def tesseramenti():
    """Ritorna l'elenco degli utenti tesserati per l'anno selezionato, seguito
    da un altro elenco, degli utenti inattivi (che non si sono tesserati) con
    il proprio saldo in cassa"""
    dbi = get_db()
    utenti = None
    utenti_tesserati = []

    if request.method == 'POST':
        error = check_inputs_quota(request.form)

        if not error:
            if 'quota' in request.form.keys():
                dbi.execute(
                    'SELECT data_inizio FROM campagne_tesseramenti'
                    ' ORDER BY data_inizio DESC'
                )
                row = dbi.fetchone()
                data_inizio = (
                    adesso() - timedelta(days=1337)
                    if isinstance(row, type(None))
                    else row['data_inizio']
                )

                if adesso() > data_inizio + timedelta(days=365):
                    dbi.execute(
                        """
                    INSERT INTO campagne_tesseramenti (data_inizio, quota)
                    VALUES (LOCALTIMESTAMP(0), %s)
                    """,
                        [request.form['quota']],
                    )
                    # Pulisco tutte le tessere invitando ad inserire la nuova
                    dbi.execute('DELETE FROM codici_ente_terzo;')

                    flash(
                        'Campagna tesseramenti avviata. Al prossimo login ad'
                        ' ogni utente sarà richiesto di confermare il'
                        ' pagamento per il tesseramento e la possibilità di'
                        ' inserire il codice della tessera dell\'ente terzo'
                        ' (se richiesta)',
                        'success',
                    )
                else:
                    flash(
                        'Non sono passati ancora 365 giorni dalla scorsa'
                        ' campagna tesseramenti. Giorni mancanti %i.'
                        % (data_inizio + timedelta(days=365) - adesso()).days,
                        'warning',
                    )

            if 'id' in request.form.keys():
                dbi.execute(
                    'SELECT data_inizio FROM campagne_tesseramenti' ' WHERE id = %s',
                    [request.form['id']],
                )
                # importo < 0 toglie il fondo cassa (FCA) che riceve
                # i soldi degli utenti
                dbi.execute(
                    """
                SELECT username, nome, cognome, cf, email, telefono
                FROM movimenti INNER JOIN utenti
                    ON movimenti.per_id_utente = utenti.id
                WHERE tipologia = 3 AND descrizione LIKE 'Tesseramento%%' AND
                    effettuato_il > %(data)s AND
                    effettuato_il < %(data)s + interval '365 days' AND
                    importo < 0
                ORDER BY nome, cognome
                """,
                    {'data': dbi.fetchone()['data_inizio']},
                )
                utenti_tesserati = dbi.fetchall()

                dbi.execute("""
                SELECT username, nome, cognome, email, telefono,
                       sum(importo) as saldo
                FROM movimenti INNER JOIN utenti
                        ON utenti.id = movimenti.per_id_utente
                WHERE movimenti.tipologia != 6
                GROUP BY username, nome, cognome, email, telefono
                ORDER BY nome, cognome
                """)
                utenti = dbi.fetchall()

        else:
            flash(error['error_msg'], 'warning')

    dbi.execute(
        'SELECT id, data_inizio FROM campagne_tesseramenti' ' ORDER BY data_inizio DESC'
    )

    return render_template(
        'auth/tesseramenti.html',
        utenti=utenti,
        utenti_tesserati=utenti_tesserati,
        campagne=dbi.fetchall(),
    )


def registra_codice_ente_terzo(id_utente, codice):
    """Inserimento del codice della tessera dell'ente terzo (es. ARCI)"""
    get_db().execute(
        """INSERT INTO codici_ente_terzo (id_utente, codice)
                        VALUES (%s, %s)
                        ON CONFLICT (id_utente) DO UPDATE SET
                        codice = EXCLUDED.codice""",
        (id_utente, codice),
    )


@bp.route('/auth/set_codice_ente_terzo', methods=['POST'])
@login_required
def set_codice_ente_terzo():
    """Inserimento o eventuale aggiornamento codice tessera ente terzo"""
    registra_codice_ente_terzo(g.user['id'], request.form['codice_ente_terzo'])

    return redirect(url_for('auth.info_utente'))


def _insert_movimento(movimento: dict):
    get_db().execute(
        """
            INSERT INTO movimenti {column_names} VALUES ({placeholders})
        """.format(
            column_names=str(tuple(cn for cn in movimento)).replace('\'', ''),
            placeholders=','.join('%s' for _ in range(len(movimento))),
        ),
        tuple(movimento.values()),
    )


@bp.route('/auth/effettua_tesseramento', methods=['POST'])
def effettua_tesseramento():
    """Inserisce il movimento nel conto dell'utente che ha appena
    autenticato con successo ma non risulta ancora tesserato,
    dell'importo campagna.quota"""
    id_utente = session.get('pending_tesseramento')
    if id_utente is None:
        return redirect(url_for('auth.login'))

    dbi = get_db()
    campagna = get_ultima_campagna_tesseramenti()

    codice_ente_terzo = request.form.get('codice_ente_terzo')
    if codice_ente_terzo:
        registra_codice_ente_terzo(id_utente, codice_ente_terzo)

    dbi.execute(
        """
            SELECT SUM(importo) as totale FROM movimenti
            WHERE per_id_utente = %s and tipologia != 6;
        """,
        [
            id_utente,
        ],
    )

    row = dbi.fetchone()
    totale = row['totale'] if row[0] else 0
    if totale < campagna['quota']:
        flash(
            'Credito insufficente per effettuare il tesseramento.'
            ' Vai alla voce Ricarica per accreditare con carta.',
            'warning',
        )
        return render_template('auth/effettua_tesseramento.html', campagna=campagna)

    if not is_tesserato(id_utente):
        inputs = {
            'tipologia': 3,
            'descrizione': 'Tesseramento {0:n}/{1:n}'.format(
                int(campagna['anno']), int(campagna['anno'] + 1)
            ),
            'effettuato_il': adesso(),
        }

        dbi.execute("SELECT id FROM utenti WHERE username = 'FCA'")
        fca_user = dbi.fetchone()

        if not fca_user:
            flash(
                'Impossibile completare il tesseramento: utente FCA non'
                ' configurato. Contattare un amministratore.',
                'warning',
            )
            return render_template('auth/effettua_tesseramento.html', campagna=campagna)

        with atomic():
            # Tolgo l'importo (valore negativo) per i gasisti
            _insert_movimento(
                inputs
                | {'per_id_utente': id_utente, 'importo': -1 * float(campagna['quota'])}
            )
            # Accredito al fondo cassa (FCA)
            _insert_movimento(
                inputs
                | {'per_id_utente': fca_user['id'], 'importo': float(campagna['quota'])}
            )

    session.clear()
    session['id_utente'] = id_utente
    return redirect(url_for('ordini.list_ordini'))
