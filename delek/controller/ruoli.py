"""Gestione dei ruoli degli utenti"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from delek.model.checks import check_inputs_ruolo
from delek.controller.auth import login_required, is_ruolo
from delek.controller.db import get_db

bp = Blueprint('ruoli', __name__, url_prefix='/ruoli')


@bp.route('/')
@login_required
@is_ruolo(['moderatore'])
def list_ruoli():
    """Elenco Ruoli"""
    get_db().execute('SELECT ruolo, descrizione FROM ruoli')

    return render_template('ruoli/list.html', ruoli=get_db().fetchall())


@bp.route('/utenti')
@login_required
@is_ruolo(['moderatore'])
def list_ruoli_utenti():
    """Elenco Ruoli"""
    get_db().execute("""
    SELECT username, nome, cognome, ruolo, descrizione
    FROM ruoli inner join arruolati ON ruoli.id = id_ruolo
               inner join utenti ON utenti.id = id_utente
    GROUP BY username, nome, cognome, ruolo, descrizione
    ORDER BY ruolo, cognome, nome, username
                     """)

    return render_template('ruoli/list_ruoli_utenti.html', ruoli=get_db().fetchall())


@bp.route('/create', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore'])
def create():
    """TODO: Ancora non gestito.
    Creazione di un Ruolo Utente"""
    if request.method == 'POST':
        error = check_inputs_ruolo(request.form)
        if not error:
            get_db().execute(
                'INSERT INTO ruoli (nome, descrizione) VALUES (%s, %s)',
                (request.form['nome'], request.form['descrizione']),
            )
            return redirect(url_for('ruoli.list_ruoli'))

        flash(error['error_msg'], 'warning')

    return render_template('ruoli/create.html')


@bp.route('/<int:idr>/update', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore'])
def update(idr):
    """UPDATE di un ruolo utente"""

    if request.method == 'POST':
        error = check_inputs_ruolo(request.form)

        if not error:
            get_db().execute(
                """
                UPDATE ruoli SET (nome, descrizione) = (%s, %s)
                WHERE id = %s
                """,
                (request.form['nome'], request.form['descrizione'], idr),
            )
            return redirect(url_for('ruoli.list'))

        flash(error['error_msg'], 'warning')

    get_db().execute('SELECT * FROM ruoli WHERE id = %s', (idr,))

    return render_template('ruoli/update.html', ruolo=get_db().fetchone())


@bp.route('/<int:idr>/delete', methods=('POST',))
@login_required
@is_ruolo(['moderatore'])
def delete(idr):
    """
    La cancellazione di un ruolo al momento corrisponde alla disattivazione
    """
    get_db().execute('UPDATE ruoli SET attivo = FALSE WHERE id = %s', (idr,))
    return redirect(url_for('ruoli.list_ruoli'))
