"""Gestione dei produttori e delle referenze collegate"""

from psycopg2.extensions import AsIs

from flask import Blueprint, flash, redirect, render_template, request, url_for

from delek.controller.auth import (
    login_required,
    is_ruolo,
    get_utenti,
    g,
    is_mod_or_ref_of,
)
from delek.model.checks import check_inputs_produttore, check_inputs_isid
from delek.model.glossary import MESI
from delek.controller.db import get_db, column_names_placeholders
from delek.controller.tempo import da_form

bp = Blueprint('produttori', __name__, url_prefix='/produttori')

COLONNE_PRODUTTORE_MODIFICABILI = (
    'nome',
    'email',
    'telefono',
    'website',
    'mask_mesi_consegna',
    'prodotto_principale',
    'descrizione',
    'attivo',
)


def build_mask_fix_inputs(inputs: dict) -> dict:
    """Fix user inputs and build mask mesi
    V: isinstance(inputs, dict) == True
    return a tuple like ('101010101010', inputs)"""
    mask = ['0' for i in range(12)]

    # CeAttivo valida contro ZERO_OR_ONE ('0'/'1' stringa): un booleano
    # Python fallirebbe sempre il regex match ("True"/"False" non è "0"/"1").
    inputs |= {'attivo': '1'}
    # Rimuovo id_utente perchè la tabella produttori non contiene questo campo,
    # per aggiungere la referenza, se presente, prendo direttamente dal form
    if 'id_utente' in inputs.keys():
        inputs.pop('id_utente')

    # tolgo il controllo per i campi che possono essere vuoti
    for prop in ['email', 'telefono', 'website', 'descrizione']:
        if not inputs[prop]:
            inputs.pop(prop)

    # Costruisco la maschera per i mesi di consegna
    for idx, mese in enumerate(MESI):
        if mese in inputs:
            inputs.pop(mese)
            mask[idx] = '1'

    return inputs | {'mask_mesi_consegna': ''.join(mask)}


def get_storico_ordini(id_produttore, data_consegna):
    """Ritorna lo storico degli ordini effettuati per `id_produttore`
    consegnati il `data_consegna`"""
    get_db().execute(
        """
        SELECT username, nome, cognome, (-1*importo) as importo,
                dettaglio
        FROM storico_ordini INNER JOIN utenti
                    ON utenti.id = storico_ordini.id_utente
        WHERE id_produttore = %s AND consegna = %s""",
        (id_produttore, data_consegna),
    )
    return get_db().fetchall()


def get_produttore(id_produttore, column_names=None):
    """Ritorna la Row associata al produttore con id_produttore"""
    get_db().execute(
        'SELECT {0} FROM produttori WHERE id = %s'.format(
            ','.join(column_names) if column_names else '*'
        ),
        [id_produttore],
    )
    return get_db().fetchone()


@bp.route('/')
def list_produttori():
    """Elenca produttori Attivi"""
    dbi = get_db()
    if 'ruoli' in g and 'moderatore' not in g.ruoli and g.referenze:
        # Elenco prima i produttori di cui sono referente poi gli altri
        dbi.execute(
            """
            SELECT * FROM produttori WHERE id = ANY (%(ref)s) UNION ALL (
             SELECT * FROM produttori WHERE id <> ALL (%(ref)s) ORDER BY nome
            )
            """,
            {'ref': g.referenze},
        )
    else:
        dbi.execute('SELECT * FROM produttori ORDER BY nome')
    produttori = dbi.fetchall()
    referenti = {
        produttore['id']: get_referenti(produttore['id']) for produttore in produttori
    }

    return render_template(
        'produttori/list.html', produttori=produttori, referenti=referenti, mesi=MESI
    )


@bp.route('/create', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def create():
    """Creazione di un produttore,
    del suo relativo listino prodotti, con la nomenclatura listino_ID
    della sua relativa tabella di ordini in corso, ordine_in_corso_ID
    dove in entrambe ID è uguale all'id numerico del produttore"""
    if request.method == 'POST':

        inputs = build_mask_fix_inputs(dict(request.form))
        # se non presente un referente, il produttore non risulta attivo
        if 'id_utente' not in request.form.keys():
            inputs['attivo'] = '0'
        error = check_inputs_produttore(inputs)

        if not error:
            dbi = get_db()

            # Whitelist esplicita: 'id' è validato da check_inputs_produttore
            # (serve altrove) ma non deve mai poter finire tra le colonne
            # scrivibili, altrimenti si sceglierebbe l'id del nuovo
            # produttore da input esterno
            inputs = {
                k: v for k, v in inputs.items() if k in COLONNE_PRODUTTORE_MODIFICABILI
            }

            column_names, placeholders = column_names_placeholders(inputs)
            dbi.execute(
                """
                INSERT INTO produttori {column_names} VALUES {placeholders}
                    RETURNING id
                """.format(column_names=column_names, placeholders=placeholders),
                tuple(inputs.values()),
            )
            id_produttore = dbi.fetchone()['id']

            if request.form['id_utente'] != 'None':
                _create_referente(id_produttore, request.form['id_utente'])

            # n_max_colli      : n max colli per gasista
            # colli_disponibili: n max colli in totale
            dbi.execute("""
            CREATE TABLE listino_{0} (
                id SERIAL PRIMARY KEY,
                categoria TEXT DEFAULT '',
                disponibile BOOLEAN DEFAULT TRUE,
                descrizione_prodotto TEXT NOT NULL,
                dettaglio_qta TEXT,
                prezzo NUMERIC(7, 2) NOT NULL,
                n_min_colli INTEGER DEFAULT 1,
                n_max_colli INTEGER DEFAULT 0,
                colli_disponibili INTEGER DEFAULT 0,
                nota TEXT);
            """.format(id_produttore))
            dbi.execute("""
            CREATE TABLE ordine_in_corso_{0} (
                id SERIAL PRIMARY KEY,
                id_utente INTEGER NOT NULL,
                id_prodotto INTEGER NOT NULL,
                colli_richiesti SMALLINT NOT NULL,
                specifica TEXT,
                effettuato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_utente) REFERENCES utenti (id),
                FOREIGN KEY (id_prodotto) REFERENCES listino_{0} (id));
            """.format(id_produttore))

            flash('Creazione Produttore avvenuta con Successo', 'success')

            return redirect(url_for('produttori.list_produttori'))

        flash(error['error_msg'], 'warning')

    return render_template('produttori/create.html', utenti=get_utenti(), mesi=MESI)


@bp.route('/<int:id_produttore>/update', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'referente'])
def update(id_produttore):
    """Aggiorna informazioni Produttore, solo se sono il referente associato o
    il moderatore"""

    if not is_mod_or_ref_of(id_produttore):
        return redirect(url_for('produttori.list_produttori'))

    produttore = get_produttore(id_produttore)
    mask_mesi = [int(c) for c in produttore['mask_mesi_consegna']]
    utenti = get_utenti()
    referenti = get_referenti(id_produttore)

    if request.method == 'POST':

        if request.form.get('id_utente'):
            error = check_inputs_isid({'id': list(request.form.values())[0]})
        else:
            inputs = build_mask_fix_inputs(dict(request.form))
            if len(get_referenti(id_produttore)) <= 0:
                inputs['attivo'] = '0'
            error = check_inputs_produttore(inputs)

        if not error:
            dbi = get_db()

            if request.form.get('id_utente'):
                _create_referente(id_produttore, request.form['id_utente'])
                flash('Aggiunta referenza avvenuta con successo', 'success')
            else:
                # Whitelist esplicita: vedi commento in create()
                inputs = {
                    k: v
                    for k, v in inputs.items()
                    if k in COLONNE_PRODUTTORE_MODIFICABILI
                }
                column_names, placeholders = column_names_placeholders(inputs)
                dbi.execute(
                    """
                    UPDATE produttori SET {column_names} = {placeholders}
                    WHERE id = %s
                    """.format(column_names=column_names, placeholders=placeholders),
                    # (v1, ..., vn, id_produttore)
                    tuple(v for v in inputs.values()) + (id_produttore,),
                )
                flash('Informazioni produttore aggiornate', 'success')

            return redirect(url_for('produttori.update', id_produttore=id_produttore))

        flash(error['error_msg'], 'warning')

    return render_template(
        'produttori/update.html',
        produttore=produttore,
        utenti=utenti,
        referenti=referenti,
        mesi=MESI,
        mask_mesi=mask_mesi,
    )


@bp.route('/<int:id_produttore>/toggle', methods=('POST',))
@login_required
@is_ruolo(['moderatore', 'referente'])
def toggle_attivo(id_produttore):
    """Cambia stato al produttore"""
    get_db().execute(
        'UPDATE produttori SET attivo = NOT attivo WHERE id = %s', (id_produttore,)
    )
    return redirect(url_for('produttori.list_produttori'))


@bp.route('/<int:id_produttore>/delete', methods=('POST',))
@login_required
@is_ruolo(['moderatore', 'referente'])
def delete(id_produttore):
    """Cancella il produttore, con relative tabelle di appoggio:
    - listino_ID
    - ordine_in_corso_ID
    """
    get_db().execute("""
        DELETE FROM produttori WHERE id = {0};
        DROP TABLE listino_{0};
        DROP TABLE ordine_in_corso_{0};
    """.format(id_produttore))
    return redirect(url_for('produttori.list_produttori'))


@bp.route('/storico/<int:id_produttore>', methods=('GET', 'POST'))
@login_required
def storico_all(id_produttore):
    """Stampa lo storico, riepilogativo di un ordine"""
    dbi = get_db()
    dbi.execute(
        """
            SELECT consegna FROM storico_ordini
            WHERE id_produttore = %s
            GROUP BY consegna ORDER BY consegna DESC
        """,
        [id_produttore],
    )
    consegne = [row['consegna'] for row in dbi.fetchall()]
    data, ordini = None, None
    if request.method == 'POST':
        try:
            if 'consegna' in request.form:
                data = da_form(request.form['consegna'])
                ordini = get_storico_ordini(id_produttore, data)
        except ValueError:
            error = 'Formato data non riconosciuto'
            flash(error, 'warning')

    if consegne:
        return render_template(
            'produttori/storico_all.html',
            id_produttore=id_produttore,
            consegne=consegne,
            data=data,
            ordini=ordini,
            totale=sum([o['importo'] for o in ordini]) if ordini else 0,
        )

    flash('Non sono presenti ordini per stampare il riepilogo', 'warning')
    return redirect(url_for('produttori.list_produttori'))


@bp.route('/storico/<int:id_storico>/utente')
@login_required
def storico_utente(id_storico):
    """Stampa lo storico di un ordine"""
    dbi = get_db()

    dbi.execute(
        """
            SELECT id_utente, (-1*importo) as importo, dettaglio
            FROM storico_ordini
            WHERE id = %s
        """,
        (id_storico,),
    )

    ordine = dbi.fetchone()

    if not ordine:
        flash('Acquisto non trovato nello storico', 'warning')
        return redirect(url_for('ordini.list_ordini'))

    if ordine['id_utente'] != g.user['id']:
        flash('Spiacente non hai i permessi di vedere questo storico', 'warning')
        return redirect(url_for('ordini.list_ordini'))

    return render_template("produttori/storico_utente.html", ordine=ordine)


# [ Referenze ] --------------------------------------------------------- {{{


def get_referenti(id_produttore=None):
    """Get tutte le referenze se id_produttore non è passato come parametro"""
    get_db().execute(
        """
        SELECT referenze.id, id_produttore, id_utente, username, nome, cognome
        FROM referenze INNER JOIN utenti ON id_utente = utenti.id
        WHERE %s = %s
        """,
        (AsIs('id_produttore'), id_produttore) if id_produttore else (1, 1),
    )

    return get_db().fetchall()


def _create_referente(id_produttore, id_utente):
    """Aggiunge una referenza, se non già presente"""
    dbi = get_db()
    dbi.execute(
        """ INSERT INTO referenze (id_produttore, id_utente)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING """,
        (id_produttore, id_utente),
    )
    # 2 = 'referente' corrisponde all' id della tabella ruoli
    # potrebbe essere preso da una select per evitare convenzioni HARDCODED
    dbi.execute(
        """ INSERT INTO arruolati (id_ruolo, id_utente)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING """,
        (2, id_utente),
    )


@bp.route('/<int:id_produttore>/<int:id_utente>/create')
@login_required
@is_ruolo(['moderatore', 'referente'])
def create_referente(id_produttore, id_utente):
    """Aggiunge una referenza tramite una richiesta HTTP"""
    _create_referente(id_produttore, id_utente)
    flash('Aggiunta Referente avvenuta con successo', 'success')
    return redirect(url_for('produttori.update', id_produttore=id_produttore))


@bp.route('/<int:id_produttore>/<int:id_utente>/delete')
@login_required
@is_ruolo(['moderatore', 'referente'])
def remove_referente(id_produttore, id_utente):
    """Rimuove una referenza"""
    get_db().execute(
        'DELETE FROM referenze WHERE id_produttore = %s and id_utente = %s',
        (id_produttore, id_utente),
    )
    flash('Rimozione Referente avvenuta con successo', 'success')
    return redirect(url_for('produttori.update', id_produttore=id_produttore))


# }}}
