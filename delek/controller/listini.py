"""Gestione dei Listini di ogni produttore"""

import csv
from io import BytesIO
from psycopg2.extensions import AsIs

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
    send_file,
)

from delek.model.checks import check_inputs_listino
from delek.controller.auth import login_required, is_ruolo
from delek.controller.db import get_db
from delek.controller.produttori import get_produttore
from delek.controller.tempo import adesso

bp = Blueprint('listini', __name__, url_prefix='/listini/<int:id_produttore>')


class CsvDialectPG(csv.Dialect):
    """Dialect per i CSV esportati con copy_to di postgresql"""

    delimiter = ','
    escapechar = '\\'
    quoting = csv.QUOTE_MINIMAL
    quotechar = '"'
    lineterminator = '\n'


def get_prodotti(id_produttore, disponibile=False):
    """Seleziono tutti i prodotti di un listino, ordinati per:
    categoria, descrizione_prodotto, dettaglio_qta
    """
    get_db().execute(
        """
            SELECT * FROM listino_{idp}
            WHERE %s = %s
            ORDER BY categoria, descrizione_prodotto, dettaglio_qta
        """.format(idp=id_produttore),
        (AsIs('disponibile'), disponibile) if disponibile else (1, 1),
    )
    return get_db().fetchall()


def get_categorie(id_produttore):
    """Ritorna tutte le categorie del produttore"""
    get_db().execute("""
                SELECT categoria as nome FROM listino_{idp}
                GROUP BY categoria
                ORDER BY categoria
            """.format(idp=id_produttore))
    return get_db().fetchall()


@bp.route('/')
def list_prodotti(id_produttore):
    """Elenco prodotti del produttore, accessibile a tutti i tipi di utenti"""

    return render_template(
        'listini/list.html',
        prodotti=get_prodotti(id_produttore),
        produttore=get_produttore(id_produttore, column_names=['id', 'nome']),
    )


@bp.route('/create', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def create(id_produttore):
    """Crea un nuovo Prodotto per la tabella listino_N N=id_produttore"""

    if request.method == 'POST':

        error = check_inputs_listino(request.form)

        if error:
            flash(error['error_msg'], 'warning')
            return render_template('listini/create.html')

        dbi = get_db()

        inputs = request.form.copy()
        inputs.pop('csrf_token', None)

        dbi.execute(
            """
                INSERT INTO listino_{idp} ({column_names})
                VALUES ({placeholders})
            """.format(
                idp=id_produttore,
                column_names=','.join(inputs.keys()),
                placeholders=','.join(['%s' for _ in enumerate(inputs)]),
            ),
            tuple(inputs.values()),
        )
        flash('Aggiunta prodotto avvenuta con successo', 'success')

        return redirect(url_for('listini.update', id_produttore=id_produttore))

    return render_template(
        'listini/create.html', categorie=get_categorie(id_produttore)
    )


@bp.route('/update', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def update(id_produttore):
    """Elenca per aggiornameto dei prodotti listino_N N=id_produttore"""
    dbi = get_db()

    if request.method == 'POST':
        error = check_inputs_listino(request.form)

        if error:
            flash(error['error_msg'] + ':' + error['input_value'], 'warning')
            return render_template(
                'listini/list-mod.html',
                prodotti=get_prodotti(id_produttore),
                produttore=get_produttore(id_produttore, column_names=['id', 'nome']),
            )

        for i, ncval in enumerate(request.form.getlist('new_categoria')):
            if request.form.getlist('old_categoria')[i] != ncval:
                dbi.execute(
                    """
                        UPDATE listino_{idp}
                        SET categoria = %s WHERE categoria = %s
                        """.format(idp=id_produttore),
                    (
                        request.form.getlist('new_categoria')[i],
                        request.form.getlist('old_categoria')[i],
                    ),
                )

        # Utilizzato getlist + range in quanto la parte con la categoria
        # bisogna evitarla altrimenti avrei potuto usare lists(), vedi:
        # werkzeug.datastructures.ImmutableMultiDict
        for i, id_prodotto in enumerate(request.form.getlist('id_prodotto')):
            dbi.execute(
                """
                    UPDATE listino_{idp}
                    SET (disponibile, descrizione_prodotto, dettaglio_qta,
                        prezzo, n_min_colli, n_max_colli, colli_disponibili,
                        nota) = ( %s, %s, %s, %s, %s, %s, %s, %s )
                    WHERE id = %s
                """.format(idp=id_produttore),
                (
                    request.form.getlist('disponibile')[i],
                    request.form.getlist('descrizione_prodotto')[i],
                    request.form.getlist('dettaglio_qta')[i],
                    request.form.getlist('prezzo')[i],
                    request.form.getlist('n_min_colli')[i],
                    request.form.getlist('n_max_colli')[i],
                    request.form.getlist('colli_disponibili')[i],
                    request.form.getlist('nota')[i],
                    id_prodotto,
                ),
            )

        flash('Aggiornamento avvenuto con successo', 'success')

    # Listino Modificabile SOLO se non vi sono ordini aperti
    # oppure se già consegnato
    dbi.execute(
        """
            SELECT id_produttore, consegna FROM dettagli_ordini
            WHERE id_produttore = %s
        """,
        (id_produttore,),
    )
    ordine_aperto = dbi.fetchone()

    if ordine_aperto and ordine_aperto['consegna'] > adesso():
        flash(
            'Non è possibile modificare il listino non consegnato o aperto', 'warning'
        )
        return redirect(url_for('listini.list_prodotti', id_produttore=id_produttore))

    return render_template(
        'listini/list-mod.html',
        prodotti=get_prodotti(id_produttore),
        produttore=get_produttore(id_produttore, column_names=['id', 'nome']),
    )


@bp.route('/esporta', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def esporta(id_produttore):
    """Esporta la tabella listino in CSV (Comma Sep. Values)"""
    content = BytesIO()
    fname = "listino-" + get_produttore(id_produttore, column_names=['nome'])['nome']
    get_db().copy_to(
        content,
        'listino_{0}'.format(id_produttore),
        sep=',',
        columns=[
            'categoria',
            'disponibile',
            'descrizione_prodotto',
            'dettaglio_qta',
            'prezzo',
            'n_min_colli',
            'n_max_colli',
            'colli_disponibili',
            'nota',
        ],
    )

    content.seek(0)
    return send_file(
        content, as_attachment=True, download_name='%s.csv' % fname, mimetype='text/csv'
    )


@bp.route('/template', methods=['GET'])
@login_required
@is_ruolo(['moderatore', 'referente'])
def scarica_template(id_produttore):
    """Scarica template CSV da compilare per importare un nuovo listino"""
    content = BytesIO(
        bytes(
            ','.join(
                [
                    'categoria',
                    'disponibile',
                    'descrizione prodotto',
                    'dettaglio quantità',
                    'prezzo',
                    'n minimo colli',
                    'n massimo colli',
                    'colli disponibili',
                    'nota',
                ]
            ),
            'utf8',
        )
    )
    return send_file(
        content,
        as_attachment=True,
        download_name='template_nuovo_listino.csv',
        mimetype='text/csv',
    )


@bp.route('/importa', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def importa(id_produttore):
    """Importa un listino da un file CSV, cancella il listino corrente"""

    if request.method == 'POST':
        dbi = get_db()

        if 'listino' not in request.files or request.files['listino'].filename == '':
            flash('Nessun file allegato da importare.', 'warning')
            return redirect(request.url)
        try:
            dbi.execute('TRUNCATE listino_{0} CASCADE'.format(id_produttore))
            fcontent = bytes(request.files['listino'].read()).decode('utf8', 'ignore')
            crr = csv.reader(fcontent.splitlines(), dialect=CsvDialectPG)

            next(crr)  # Escludo prima riga con nomi colonne
            for row in crr:
                if len(row) != 9:
                    flash(
                        'Le colonne alla riga (%s) non corrispondono' % row, 'warning'
                    )
                    return redirect(request.url)

                dbi.execute(
                    """
                    INSERT INTO listino_{0}
                    (categoria, disponibile, descrizione_prodotto,
                    dettaglio_qta, prezzo, n_min_colli, n_max_colli,
                    colli_disponibili, nota)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """.format(id_produttore),
                    [
                        row[0],
                        bool(row[1]) if row[1] else True,
                        row[2],
                        row[3],
                        float(row[4]),
                        int(row[5]) if row[5] else 1,
                        int(row[6]) if row[6] else 0,
                        int(row[7]) if row[7] else 0,
                        row[8],
                    ],
                )

            flash('Aggiornamento listino avvenuto correttamente', 'success')
            return redirect(
                url_for('listini.list_prodotti', id_produttore=id_produttore)
            )

        except TypeError as terr:
            print(terr)

            flash('Sono stati riscontrati errori nella lettura del file', 'warning')
            return redirect(request.url)

    return render_template('listini/importa.html', id_produttore=id_produttore)


@bp.route('/<int:id_prodotto>/delete', methods=('GET',))
@login_required
@is_ruolo(['moderatore', 'referente'])
def delete(id_produttore, id_prodotto):
    """Cancella il Prodotto tramite il proprio id"""

    get_db().execute(
        'DELETE FROM listino_{idl} WHERE id = %s'.format(idl=id_produttore),
        (id_prodotto,),
    )

    flash('Rimozione del prodotto avvenuta con successo', 'success')

    return redirect(url_for('listini.update', id_produttore=id_produttore))
