""" Istruzioni """
import re

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)
from markupsafe import Markup, escape

from delek.controller.auth import login_required, is_ruolo
from delek.controller.db import get_db
from delek.model.checks import check_inputs_contenuto

bp = Blueprint('istruzioni', __name__, url_prefix='/istruzioni')

_URL_RE = re.compile(r'(https?://[^\s<>"]+)')


@bp.app_template_filter('urlize')
def urlize(text):
    """ Escapa il testo (nessun HTML digitato da un moderatore viene mai
    interpretato) e poi trasforma gli URL http/https in link cliccabili:
    permette di condividere risorse esterne nei blocchi di testo libero
    senza dover abilitare l'editing HTML/Markdown. """
    escaped = str(escape(text or ''))
    linked = _URL_RE.sub(
        lambda m: '<a href="{0}" rel="noopener noreferrer">{0}</a>'.format(
            m.group(1)),
        escaped)
    return Markup(linked)

# Ogni blocco di testo modificabile ha un default (usato finché nessun
# moderatore lo personalizza) e la pagina a cui si torna dopo il salvataggio.
CONTENUTI = {
    'acquisto_intro': {
        'endpoint': 'istruzioni.acquisto',
        'default': """I pagamenti degli ordini avvengono con il metodo del prepagato.

Cosa significa? Abbiamo aperto un conto corrente dedicato al GAS (al punto 1, di seguito, troverete le coordinate del conto). Ogni gasista versa una somma nel conto corrente. L'importo è a discrezione del singolo.

Il gasista non paga mai in contanti: l'importo che spende viene automaticamente detratto dal suo credito al momento dell'ordine.

Un esempio: io verso oggi 100 euro nel nostro conto corrente a mio nome. Acquisto 11 euro di formaggi, 4 euro di pane e 3 euro di miele. Quando vado a ritirare i prodotti non ho bisogno di pagare. In credito sul sito non avrò più 100 euro, ma 82 euro (100-18). E così via di ordine in ordine.

I debiti vengono infatti scalati al momento dell'ordine, prima del ritiro della merce. Questo per essere sicuri di avere i soldi per pagare i fornitori senza che gli incaricati a fare i bonifici siano mai costretti a dovere anticipare somme proprie.

Quando il costo della merce consegnata differisce dall'ordine, il referente fa una rettifica, e il credito residuo viene pertanto corretto. Si invitano comunque i gasisti a tenere sotto controllo la situazione del loro credito; sviste segnalate a distanza di troppo tempo potrebbero essere difficili da gestire.

Quando mi accorgo che i soldi stanno finendo (vedi punto 3) effettuo un altro versamento.

Attenzione! Ricordatevi che da quando fate il bonifico al momento nel quale troverete i soldi accreditati sul conto GAS possono passare anche diversi giorni (fino a 1 settimana) quindi calcolate bene i tempi se avete un ordine in programma.

Questo è il semplice funzionamento, ovvero ciò che ogni gasista ha bisogno di sapere per aderire al prepagato. Ciò che il singolo gasista che acquista deve fare è semplicemente versare soldi nel conto corrente e sincerarsi che il suo saldo sia sempre più o meno sufficiente per far fronte ai suoi acquisti.""",
    },
    # Link a risorse esterne (es. un documento condiviso di FAQ): vuoto di
    # default, non ha senso spedire link altrui come esempio.
    'list_link_esterni': {
        'endpoint': 'istruzioni.list_tutorial',
        'default': '',
    },
    # Come sopra, ma per l'elenco di eventuali video tutorial.
    'list_video_tutorial': {
        'endpoint': 'istruzioni.list_tutorial',
        'default': '',
    },
}


def get_contenuto(slug):
    """ Ritorna il testo modificabile per slug, o il default hardcoded se
    nessun moderatore l'ha ancora personalizzato per questa istanza """
    get_db().execute(
        'SELECT contenuto FROM contenuti_editabili WHERE slug = %s', [slug])
    row = get_db().fetchone()
    return row['contenuto'] if row else CONTENUTI[slug]['default']


@bp.route('/acquisto')
def acquisto():
    """ pagina statica con le istruzioni per gli acquisti, con
    un'introduzione modificabile dai moderatori """
    return render_template('istruzioni/acquisto.html',
                           contenuto_intro=get_contenuto('acquisto_intro'))


@bp.route('/list')
def list_tutorial():
    """ pagina statica con i video tutorial, con link esterni e video
    modificabili dai moderatori """
    return render_template(
        'istruzioni/list.html',
        contenuto_link_esterni=get_contenuto('list_link_esterni'),
        contenuto_video_tutorial=get_contenuto('list_video_tutorial'))


@bp.route('/modifica/<slug>', methods=('GET', 'POST'))
@login_required
@is_ruolo(['moderatore'])
def modifica(slug):
    """ Modifica di un blocco di testo di CONTENUTI (solo moderatori) """
    if slug not in CONTENUTI:
        abort(404)

    if request.method == 'POST':
        error = check_inputs_contenuto(request.form)
        if not error:
            get_db().execute("""
                INSERT INTO contenuti_editabili
                    (slug, contenuto, aggiornato_da)
                VALUES (%s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    contenuto = EXCLUDED.contenuto,
                    aggiornato_il = CURRENT_TIMESTAMP,
                    aggiornato_da = EXCLUDED.aggiornato_da
                """, (slug, request.form['contenuto'], g.user['id']))
            flash('Contenuto aggiornato con successo', 'success')
            return redirect(url_for(CONTENUTI[slug]['endpoint']))
        flash(error['error_msg'], 'warning')

    return render_template(
        'istruzioni/modifica.html', slug=slug,
        contenuto=request.form.get('contenuto') or get_contenuto(slug))
