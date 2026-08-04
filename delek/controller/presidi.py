"""Gestione dei Presidi"""

from datetime import datetime, timedelta

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from delek.model.checks import check_inputs_isid
from delek.controller.auth import is_ruolo, login_required
from delek.controller.db import get_db
from delek.controller.tempo import FUSO, adesso, da_form

bp = Blueprint('presidi', __name__, url_prefix='/presidi')


def get_giorni_presidi(year, when=2):  # 2 = Mercoledì
    """Ritorna tutti i mercoledi di un anno"""
    today = adesso()
    day = datetime(year, 1, 1, 19, tzinfo=FUSO)
    day += timedelta(
        days=when - day.weekday() if day.weekday() <= when else 7 + when - day.weekday()
    )
    while day.year == year:
        if day >= today:
            yield day
        day += timedelta(days=7)


def get_date_con_presidiante():
    """Ritorna una lista di date, che sono coperte da almeno un predisiante"""
    get_db().execute("""
            SELECT giorno FROM presidi
            WHERE giorno >= now() AND id_utente NOTNULL
        """)

    return [row['giorno'] for row in get_db().fetchall()]


def get_presidi():
    """Ritorna l'elenco degli id utente che si sono iscritti a presidi"""
    get_db().execute("""
        SELECT giorno, id_utente FROM presidi
        WHERE id_utente IS NOT NULL AND
            EXTRACT(YEAR FROM giorno) = EXTRACT(YEAR FROM CURRENT_DATE)
        """)
    return get_db().fetchall()


@bp.route('/clear')
@login_required
@is_ruolo(['moderatore', 'presidi'])
def clear():
    """Pulisce le righe dei presidi passati"""
    get_db().execute("""
        DELETE FROM presidi
        WHERE extract('year' from giorno) != extract('year' from now())
        """)
    return redirect(url_for('presidi.list_presidi'))


@bp.route('/newy')
@login_required
@is_ruolo(['moderatore', 'presidi'])
def newy():
    """Genera le date che non sono ancora state inserite nell'anno in corso"""
    dbi = get_db()

    for giorno in get_giorni_presidi(datetime.today().year):
        dbi.execute('INSERT INTO presidi (giorno) VALUES (%s)', [giorno])
        dbi.execute('INSERT INTO presidi (giorno) VALUES (%s)', [giorno])

    return redirect(url_for('presidi.list_presidi'))


@bp.route('/')
@login_required
def list_presidi():
    """Elenco Presidi"""
    dbi = get_db()

    dbi.execute("""
            SELECT presidi.id, giorno, id_utente,
                    username, nome, cognome, email, telefono
            FROM presidi LEFT JOIN utenti ON id_utente = utenti.id
            WHERE giorno >= now()
            ORDER BY giorno
        """)

    return render_template('presidi/list.html', presidi=dbi.fetchall())


@bp.route('/passati')
@login_required
def list_presidi_passati():
    """Elenco Presidi Passati"""
    dbi = get_db()

    dbi.execute("""
            SELECT presidi.id, giorno, id_utente,
                    username, nome, cognome, email, telefono
            FROM presidi LEFT JOIN utenti ON id_utente = utenti.id
            WHERE giorno < now() AND username != ''
            ORDER BY giorno
        """)

    return render_template('presidi/passati.html', presidi=dbi.fetchall())


@bp.route('/vademecum')
def vademecum():
    '''Mostra pagina con vademecum'''
    return render_template('presidi/vademecum.html')


@bp.route('/stats')
def stats():
    '''Mostra statistiche presidianti'''

    get_db().execute("""
    SELECT nome, cognome, username, telefono, email FROM utenti
    WHERE id NOT IN (SELECT id_utente FROM presidi
                        WHERE id_utente IS NOT NULL) AND
          id NOT IN (SELECT DISTINCT id_utente FROM arruolati)
    ORDER BY nome
    """)

    return render_template('presidi/stats.html', utenti=get_db().fetchall())


@bp.route('/create', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'presidi'])
def create():
    """Creazione di un Presidio"""
    msg = {'content': 'Formato data non conforme', 'type': 'warning'}
    if request.method == 'POST':
        try:
            get_db().execute(
                'INSERT INTO presidi (giorno) VALUES (%s)',
                (da_form(request.form['giorno']) + timedelta(hours=19),),
            )
            msg = {'content': 'Inserimento avvenuto con successo', 'type': 'success'}
        except ValueError:
            pass

    flash(msg['content'], msg['type'])

    return redirect(url_for('presidi.list_presidi'))


def _aggiungi_ruolo(id_utente, id_presidio):
    dbi = get_db()
    dbi.execute(
        'UPDATE presidi SET id_utente = %s WHERE id = %s', (id_utente, id_presidio)
    )

    dbi.execute("SELECT id FROM ruoli WHERE ruolo = 'presidiante'")
    id_ruolo = dbi.fetchone()['id']
    dbi.execute(
        """
            SELECT 1 FROM arruolati
            WHERE id_ruolo = %s AND id_utente = %s
            """,
        (id_ruolo, id_utente),
    )
    esistente = dbi.fetchone()

    if not esistente:
        dbi.execute(
            """
                INSERT INTO arruolati (id_ruolo, id_utente)
                VALUES (%s, %s)
                """,
            (id_ruolo, id_utente),
        )


@bp.route('/booking')
@login_required
def booking():
    """Creazione di un Presidio"""
    id_presidio = request.args.get('id_presidio')
    error = check_inputs_isid({'id': id_presidio})
    if error:
        flash(error['error_msg'], 'warning')
    else:
        _aggiungi_ruolo(g.user['id'], id_presidio)
        flash('Prenotazione avvenuta con successo', 'success')

    return redirect(url_for('presidi.list_presidi'))


def _aggiorna_ruolo(id_presidio):
    dbi = get_db()

    dbi.execute("SELECT id FROM ruoli WHERE ruolo = 'presidiante'")
    id_ruolo = dbi.fetchone()['id']

    dbi.execute('SELECT id_utente FROM presidi WHERE id = %s', (id_presidio,))
    id_utente = dbi.fetchone()['id_utente']

    # Verifica se l'utente ha altri presidi con lo stesso ruolo
    dbi.execute('SELECT * FROM presidi WHERE id_utente = %s', (id_utente,))
    altri_presidi = dbi.fetchone()
    if not altri_presidi:
        dbi.execute(
            """
            DELETE FROM arruolati
            WHERE id_ruolo = %s AND id_utente = %s
            """,
            (id_ruolo, id_utente),
        )


@bp.route('/unbooking/<int:id_presidio>')
@login_required
def unbooking(id_presidio):
    """Rimozione di una prenotazione presidio"""
    dbi = get_db()

    # Rimuovi la prenotazione
    dbi.execute('UPDATE presidi SET id_utente = NULL WHERE id = %s', (id_presidio,))
    _aggiorna_ruolo(id_presidio)

    flash('Rimozione Prenotazione avvenuta con successo', 'success')

    return redirect(url_for('presidi.list_presidi'))


@bp.route('/assign/<int:id_presidio>', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'presidi'])
def assign(id_presidio):
    """Assegna un utente a un presidio"""
    dbi = get_db()

    if request.method == 'POST':
        error = check_inputs_isid({'id': request.form.get('id_utente')})

        if not error:
            id_utente = request.form.get('id_utente')

            _aggiungi_ruolo(id_utente, id_presidio)

            flash('Assegnazione presidiante avvenuta con successo', 'success')
            return redirect(url_for('presidi.list_presidi'))

        flash('Errore durante assegnazione, id non valido', 'warning')

    dbi.execute('SELECT * FROM utenti ORDER BY nome, cognome, username')

    return render_template('presidi/assign.html', utenti=dbi.fetchall())


@bp.route('/<int:id_presidio>/delete', methods=('GET',))
@login_required
@is_ruolo(['moderatore', 'presidi'])
def delete(id_presidio):
    """Cancella la data di presidio tramite il proprio id"""

    get_db().execute('DELETE FROM presidi WHERE id = %s', (id_presidio,))
    _aggiorna_ruolo(id_presidio)

    flash('Rimozione del presidio avvenuta con successo', 'success')

    return redirect(url_for('presidi.list_presidi'))
