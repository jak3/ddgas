"""Import dell'estratto conto per accreditare le ricariche via bonifico.

Riusa il meccanismo provider-agnostico già in pagamenti.py
(ricariche_esterne, registra_pagamento_creato()/conferma_pagamento()): un
bonifico è solo un altro 'provider' in quello stesso schema. righe_estratto_
conto è uno stadio intermedio che esiste solo per il periodo in cui il
destinatario non è ancora noto (nessuna dichiarazione, nessun match sulla
causale) o non è univoco: appena lo diventa, l'accredito vero e proprio
passa sempre da registra_pagamento_creato()/conferma_pagamento(), mai da una
scrittura diretta su movimenti.
"""

import csv
import io
import re
import secrets
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from delek.controller.auth import get_utenti, is_ruolo, login_required
from delek.controller.db import atomic, get_db
from delek.controller.pagamenti import (
    IMPORTO_MASSIMO,
    IMPORTO_MINIMO,
    conferma_pagamento,
    registra_pagamento_creato,
)
from delek.model.checks import check_inputs_configurazione_estratto_conto

bp = Blueprint('estratto_conto', __name__, url_prefix='/estratto-conto')

FORMATI_DATA = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']
ENCODING_DISPONIBILI = ['utf-8', 'latin-1', 'cp1252']
SEPARATORI_CSV = [',', ';', '|']


def _normalizza(testo):
    """Lowercase + spazi collassati: confronto stabile sulla causale."""
    return ' '.join(testo.lower().split())


def get_configurazione():
    """Configurazione corrente di parsing del CSV, o None se un moderatore
    non l'ha ancora impostata per questa installazione."""
    get_db().execute('SELECT * FROM configurazione_estratto_conto WHERE id = 1')
    return get_db().fetchone()


def _parse_righe(file_storage, config):
    """Parsa l'intero file secondo `config`, ritorna la lista di righe con
    importo positivo (le uscite non sono ricariche, non c'è nulla con cui
    farle combaciare). Solleva ValueError con un messaggio puntuale sulla
    prima riga non conforme: tutto o niente, niente import parziale su un
    file mal formato."""
    raw = file_storage.read().decode(config['encoding'], 'ignore')
    reader = csv.DictReader(io.StringIO(raw), delimiter=config['separatore_csv'])

    righe = []
    for numero_riga, row in enumerate(reader, start=2):  # riga 1 = intestazione
        try:
            data_valuta = datetime.strptime(
                row[config['colonna_data']].strip(), config['formato_data']
            ).date()
            causale = row[config['colonna_causale']].strip()
            importo_raw = row[config['colonna_importo']].strip()
            if config['decimale_virgola']:
                importo_raw = importo_raw.replace('.', '').replace(',', '.')
            # Decimal solo per la conversione, senza artefatti di
            # arrotondamento del float: subito dopo si torna a float, per
            # coerenza col resto del codebase (movimenti.py/pagamenti.py
            # non usano mai Decimal).
            importo = float(Decimal(importo_raw))
        except (KeyError, ValueError, InvalidOperation, AttributeError) as exc:
            raise ValueError(
                'Riga {0} non valida: colonne o formato non conformi alla'
                ' configurazione impostata ({1})'.format(numero_riga, exc)
            ) from exc

        if importo > 0:
            righe.append(
                {'data_valuta': data_valuta, 'causale': causale, 'importo': importo}
            )

    return righe


def _inserisci_righe_nuove(righe, id_utente_caricamento):
    """Deduplica per conteggio: per ogni tripla (data, causale, importo) nel
    file, inserisce solo le occorrenze in eccesso rispetto a quelle già
    presenti in DB (gestisce sia il caso comune di export con date
    sovrapposte, sia due bonifici realmente identici nello stesso giorno).
    Tutto dentro un lock advisory per la durata dell'inserimento, così due
    import concorrenti non possono duplicare le stesse righe (il lock si
    rilascia da solo a fine transazione). Ritorna gli id delle righe nuove."""
    dbi = get_db()
    gruppi = Counter((r['data_valuta'], r['causale'], r['importo']) for r in righe)
    nuove_id = []

    with atomic():
        dbi.execute("SELECT pg_advisory_xact_lock(hashtext('estratto_conto_import'))")

        for (data_valuta, causale, importo), n_nel_file in gruppi.items():
            dbi.execute(
                """
                SELECT COUNT(*) AS n FROM righe_estratto_conto
                WHERE data_valuta = %s AND causale = %s AND importo = %s
                """,
                (data_valuta, causale, importo),
            )
            n_esistenti = dbi.fetchone()['n']

            for _ in range(max(0, n_nel_file - n_esistenti)):
                dbi.execute(
                    """
                    INSERT INTO righe_estratto_conto
                        (data_valuta, causale, importo, caricato_da)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (data_valuta, causale, importo, id_utente_caricamento),
                )
                nuove_id.append(dbi.fetchone()['id'])

    return nuove_id


def trova_candidati(riga):
    """Ritorna (set di id_utente candidati, dichiarazioni pendenti con
    importo compatibile) per una riga di estratto conto: unione di chi ha
    dichiarato un versamento dello stesso importo e di chi è identificato
    nella causale (username/email/nome cognome/codice RIC-<id>)."""
    dbi = get_db()
    dbi.execute(
        """
        SELECT id_utente, provider_ref FROM ricariche_esterne
        WHERE provider = 'bonifico' AND stato = 'creato' AND importo = %s
        """,
        (riga['importo'],),
    )
    dichiarazioni = dbi.fetchall()
    candidati = {d['id_utente'] for d in dichiarazioni}

    causale_norm = _normalizza(riga['causale'])
    for utente in get_utenti(vincolo=('attivo', True)):
        identificatori = ['ric-{0}'.format(utente['id']), utente['username']]
        if utente['nome'] and utente['cognome']:
            identificatori.append('{0} {1}'.format(utente['nome'], utente['cognome']))
        if utente['email']:
            identificatori.append(utente['email'])

        for identificatore in identificatori:
            i_norm = _normalizza(identificatore)
            # Confini di parola: 'ric-1' non deve combaciare dentro 'ric-12'.
            # Identificatori troppo corti (<3 char) esclusi per evitare
            # falsi positivi da coincidenze in testo libero.
            if len(i_norm) >= 3 and re.search(
                r'\b' + re.escape(i_norm) + r'\b', causale_norm
            ):
                candidati.add(utente['id'])
                break

    return candidati, dichiarazioni


def _segna_riga_accreditata(id_riga, id_utente, provider_ref):
    dbi = get_db()
    dbi.execute(
        "SELECT id_movimento FROM ricariche_esterne"
        " WHERE provider = 'bonifico' AND provider_ref = %s",
        (provider_ref,),
    )
    id_movimento = dbi.fetchone()['id_movimento']
    dbi.execute(
        """
        UPDATE righe_estratto_conto
        SET stato = 'accreditato', id_utente = %s, id_movimento = %s
        WHERE id = %s
        """,
        (id_utente, id_movimento, id_riga),
    )


def risolvi_automaticamente(riga):
    """Se trova_candidati() risolve a un solo utente, accredita subito:
    riusa il provider_ref della dichiarazione pendente se il candidato viene
    da lì, altrimenti crea+conferma con provider_ref='riga-<id>' (mai un
    token casuale: deterministico sull'id della riga, così un tentativo
    ripetuto sulla stessa riga non accredita due volte). Ritorna True se ha
    accreditato ora."""
    candidati, dichiarazioni = trova_candidati(riga)
    if len(candidati) != 1:
        return False

    id_utente = next(iter(candidati))
    dichiarazione = next(
        (d for d in dichiarazioni if d['id_utente'] == id_utente), None
    )
    provider_ref = (
        dichiarazione['provider_ref']
        if dichiarazione
        else 'riga-{0}'.format(riga['id'])
    )

    registra_pagamento_creato('bonifico', provider_ref, id_utente, riga['importo'])
    if not conferma_pagamento('bonifico', provider_ref):
        return False

    _segna_riga_accreditata(riga['id'], id_utente, provider_ref)
    return True


@bp.route('/dichiara', methods=('GET', 'POST'))
@login_required
def dichiara():
    """Un gasista dichiara di aver fatto un bonifico: se l'importo coincide
    con un'unica riga dell'estratto conto (aiutato dalla causale in caso di
    ambiguità), l'accredito parte in automatico al prossimo import."""
    if request.method == 'POST':
        try:
            importo = float(request.form['importo'])
        except (KeyError, ValueError):
            flash('Importo non valido', 'warning')
            return render_template('estratto_conto/dichiara.html')

        if not IMPORTO_MINIMO <= importo <= IMPORTO_MASSIMO:
            flash(
                'Importo non valido: deve essere tra {0} e {1} euro'.format(
                    IMPORTO_MINIMO, IMPORTO_MASSIMO
                ),
                'warning',
            )
            return render_template('estratto_conto/dichiara.html')

        registra_pagamento_creato(
            'bonifico', secrets.token_hex(8), g.user['id'], importo
        )
        flash(
            "Dichiarazione registrata: il credito comparirà dopo il prossimo"
            " caricamento dell'estratto conto.",
            'success',
        )
        return redirect(url_for('estratto_conto.dichiara'))

    return render_template('estratto_conto/dichiara.html')


@bp.route('/configurazione', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore'])
def configurazione():
    """Impostazioni di parsing del CSV, modificabili in qualunque momento
    (non solo al setup): banche diverse, e può cambiare nel tempo."""
    if request.method == 'POST':
        error = check_inputs_configurazione_estratto_conto(request.form)
        if not error:
            get_db().execute(
                """
                INSERT INTO configurazione_estratto_conto
                    (id, colonna_data, colonna_causale, colonna_importo,
                     formato_data, separatore_csv, decimale_virgola,
                     encoding, aggiornato_da)
                VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    colonna_data = EXCLUDED.colonna_data,
                    colonna_causale = EXCLUDED.colonna_causale,
                    colonna_importo = EXCLUDED.colonna_importo,
                    formato_data = EXCLUDED.formato_data,
                    separatore_csv = EXCLUDED.separatore_csv,
                    decimale_virgola = EXCLUDED.decimale_virgola,
                    encoding = EXCLUDED.encoding,
                    aggiornato_il = CURRENT_TIMESTAMP,
                    aggiornato_da = EXCLUDED.aggiornato_da
                """,
                (
                    request.form['colonna_data'],
                    request.form['colonna_causale'],
                    request.form['colonna_importo'],
                    request.form['formato_data'],
                    request.form['separatore_csv'],
                    request.form.get('decimale_virgola') == '1',
                    request.form['encoding'],
                    g.user['id'],
                ),
            )
            flash('Configurazione aggiornata con successo', 'success')
            return redirect(url_for('estratto_conto.configurazione'))
        flash(error['error_msg'], 'warning')

    return render_template(
        'estratto_conto/configurazione.html',
        configurazione=get_configurazione(),
        formati_data=FORMATI_DATA,
        encoding_disponibili=ENCODING_DISPONIBILI,
        separatori_csv=SEPARATORI_CSV,
    )


@bp.route('/importa', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def importa():
    """Carica un estratto conto: le righe nuove (deduplicate rispetto a
    import precedenti sovrapposti) vengono matchate in automatico dove
    possibile, il resto va nella coda di risoluzione manuale."""
    config = get_configurazione()
    if not config:
        flash(
            'Configura prima il formato del CSV per questa installazione.',
            'warning',
        )
        return redirect(url_for('estratto_conto.configurazione'))

    if request.method == 'POST':
        if (
            'estratto' not in request.files
            or request.files['estratto'].filename == ''
        ):
            flash('Nessun file allegato da importare.', 'warning')
            return redirect(request.url)

        try:
            righe = _parse_righe(request.files['estratto'], config)
        except ValueError as exc:
            flash(str(exc), 'warning')
            return redirect(request.url)

        nuove_id = _inserisci_righe_nuove(righe, g.user['id'])

        n_accreditate = 0
        for id_riga in nuove_id:
            get_db().execute(
                'SELECT * FROM righe_estratto_conto WHERE id = %s', (id_riga,)
            )
            riga = get_db().fetchone()
            if risolvi_automaticamente(riga):
                n_accreditate += 1

        flash(
            'Estratto conto importato: {0} righe nuove, {1} accreditate in'
            ' automatico, {2} da verificare a mano.'.format(
                len(nuove_id), n_accreditate, len(nuove_id) - n_accreditate
            ),
            'success',
        )
        return redirect(url_for('estratto_conto.coda'))

    return render_template('estratto_conto/importa.html')


@bp.route('/coda')
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def coda():
    """Righe non risolte in automatico, coi candidati (se presenti)
    ricalcolati al volo per suggerire una scelta al tesoriere."""
    get_db().execute(
        "SELECT * FROM righe_estratto_conto WHERE stato = 'da_verificare'"
        " ORDER BY data_valuta"
    )
    righe = get_db().fetchall()

    suggerimenti = {riga['id']: trova_candidati(riga)[0] for riga in righe}

    return render_template(
        'estratto_conto/coda.html',
        righe=righe,
        suggerimenti=suggerimenti,
        utenti=get_utenti(vincolo=('attivo', True)),
    )


@bp.route('/risolvi/<int:id_riga>', methods=('POST',))
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def risolvi(id_riga):
    """Il tesoriere sceglie manualmente l'utente da accreditare per una riga
    rimasta ambigua. provider_ref deterministico ('riga-<id>'): un secondo
    submit della stessa richiesta (doppio click, retry del browser) collide
    sullo stesso provider_ref e non accredita due volte."""
    try:
        id_utente = int(request.form['id_utente'])
    except (KeyError, ValueError):
        flash('Seleziona un utente', 'warning')
        return redirect(url_for('estratto_conto.coda'))

    get_db().execute(
        "SELECT * FROM righe_estratto_conto WHERE id = %s AND stato = 'da_verificare'",
        (id_riga,),
    )
    riga = get_db().fetchone()
    if not riga:
        flash('Riga non trovata o già risolta', 'warning')
        return redirect(url_for('estratto_conto.coda'))

    provider_ref = 'riga-{0}'.format(id_riga)
    registra_pagamento_creato('bonifico', provider_ref, id_utente, riga['importo'])
    conferma_pagamento('bonifico', provider_ref)
    _segna_riga_accreditata(id_riga, id_utente, provider_ref)

    flash('Riga accreditata con successo', 'success')
    return redirect(url_for('estratto_conto.coda'))


@bp.route('/scarta/<int:id_riga>', methods=('POST',))
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def scarta(id_riga):
    """La riga non è una ricarica (pagamento a un fornitore, commissione
    bancaria, ecc. che compare comunque nell'estratto conto): nessun
    accredito."""
    get_db().execute(
        "UPDATE righe_estratto_conto SET stato = 'scartato'"
        " WHERE id = %s AND stato = 'da_verificare'",
        (id_riga,),
    )
    flash('Riga scartata', 'success')
    return redirect(url_for('estratto_conto.coda'))
