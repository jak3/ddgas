""" Ricariche del proprio conto tramite gateway di pagamento esterni.

Le funzioni registra_pagamento_creato()/conferma_pagamento()/
annulla_pagamento() sono provider-agnostiche e vanno riusate da qualunque
nuovo adattatore (Satispay, PayPal, ...): tengono traccia dello stato in
ricariche_esterne e garantiscono che una stessa notifica ricevuta più volte
dal gateway non accrediti (o storni) due volte lo stesso pagamento. La
parte sotto "Stripe" è invece specifica di quel provider (creazione della
sessione di pagamento e verifica della firma del webhook).
"""
import base64
import hashlib
import json
import os
from email.utils import formatdate
from urllib.parse import urlsplit

import requests
import stripe
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from delek.controller.auth import login_required, is_ruolo
from delek.controller.db import get_db, atomic
from delek.controller.movimenti import insert_movimento
from delek.extensions import csrf

bp = Blueprint('pagamenti', __name__, url_prefix='/pagamenti')

IMPORTO_MINIMO = 1
IMPORTO_MASSIMO = 2000


def registra_pagamento_creato(provider, provider_ref, id_utente, importo):
    """ Traccia una richiesta di pagamento avviata, prima della conferma da
    parte del gateway. """
    get_db().execute("""
        INSERT INTO ricariche_esterne
            (provider, provider_ref, id_utente, importo)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (provider, provider_ref) DO NOTHING
        """, (provider, provider_ref, id_utente, importo))


def conferma_pagamento(provider, provider_ref):
    """ Accredita il movimento corrispondente a un pagamento confermato dal
    gateway. Idempotente: una stessa notifica ricevuta più volte (i gateway
    di pagamento ritentano le notifiche non confermate in tempo) non
    accredita due volte. Ritorna True se ha accreditato ora, False se il
    pagamento era già stato gestito o non risulta tracciato. """
    dbi = get_db()

    with atomic():
        dbi.execute("""
            SELECT * FROM ricariche_esterne
            WHERE provider = %s AND provider_ref = %s
            FOR UPDATE
            """, (provider, provider_ref))
        pagamento = dbi.fetchone()

        if not pagamento or pagamento['stato'] == 'completato':
            return False

        insert_movimento({
            'tipologia': 1,  # versamento
            'per_id_utente': pagamento['id_utente'],
            'descrizione': '[Ricarica {0}] Versamento automatico'.format(
                provider),
            'importo': float(pagamento['importo']),
        })
        dbi.execute("""
            UPDATE ricariche_esterne SET stato = 'completato'
            WHERE provider = %s AND provider_ref = %s
            """, (provider, provider_ref))

    return True


def annulla_pagamento(provider, provider_ref, motivo):
    """ Gemella di conferma_pagamento(), per i due casi in cui un pagamento
    tracciato non va a buon fine: un rimborso dopo l'accredito (stato
    'completato' -> 'rimborsato', con uno storno registrato in movimenti) o
    un pagamento mai arrivato a completamento (stato 'creato' -> 'fallito',
    nessun movimento da stornare perché non ne era mai stato creato uno).
    Idempotente come conferma_pagamento(): un pagamento già rimborsato/
    fallito, o mai tracciato, non viene ritoccato. Ritorna True se ha agito
    ora, False altrimenti. """
    dbi = get_db()

    with atomic():
        dbi.execute("""
            SELECT * FROM ricariche_esterne
            WHERE provider = %s AND provider_ref = %s
            FOR UPDATE
            """, (provider, provider_ref))
        pagamento = dbi.fetchone()

        if not pagamento or pagamento['stato'] not in ('creato', 'completato'):
            return False

        if pagamento['stato'] == 'completato':
            nuovo_stato = 'rimborsato'
            insert_movimento({
                'tipologia': 5,  # rettifica
                'per_id_utente': pagamento['id_utente'],
                'descrizione': '[Ricarica {0}] Storno per {1}'.format(
                    provider, motivo),
                'importo': -float(pagamento['importo']),
            })
        else:
            nuovo_stato = 'fallito'

        dbi.execute("""
            UPDATE ricariche_esterne
            SET stato = %s
            WHERE provider = %s AND provider_ref = %s
            """, (nuovo_stato, provider, provider_ref))

    return True


# --- Stripe -----------------------------------------------------------

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


@bp.route('/ricarica', methods=('GET', 'POST'))
@login_required
def ricarica():
    """ Pagina di ricarica: l'utente sceglie un importo e viene rediretto
    alla pagina di pagamento ospitata da Stripe (Stripe Checkout: nessuna
    integrazione JS lato nostro, nessun dato di carta passa dal nostro
    server). """
    if request.method == 'POST':
        try:
            importo = float(request.form['importo'])
        except (KeyError, ValueError):
            flash('Importo non valido', 'warning')
            return render_template('pagamenti/ricarica.html')

        if not IMPORTO_MINIMO <= importo <= IMPORTO_MASSIMO:
            flash('Importo non valido: deve essere tra {0} e {1} euro'
                  .format(IMPORTO_MINIMO, IMPORTO_MASSIMO), 'warning')
            return render_template('pagamenti/ricarica.html')

        checkout_session = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': 'Ricarica conto'},
                    'unit_amount': round(importo * 100),
                },
                'quantity': 1,
            }],
            success_url=url_for('pagamenti.ricarica_completata',
                                _external=True),
            cancel_url=url_for('pagamenti.ricarica', _external=True),
        )
        registra_pagamento_creato('stripe', checkout_session.id,
                                  g.user['id'], importo)

        return redirect(checkout_session.url, code=303)

    return render_template('pagamenti/ricarica.html')


@bp.route('/ricarica/completata')
@login_required
def ricarica_completata():
    """ L'utente torna qui dopo il pagamento su Stripe. Il credito viene
    accreditato dal webhook (unica fonte affidabile: solo Stripe può
    confermare che il pagamento sia davvero riuscito), non da questa
    pagina — che quindi mostra solo un messaggio, senza inserire nulla. """
    flash('Pagamento in elaborazione: il credito comparirà a breve sul tuo'
          ' conto se avvenuto correttamente.', 'success')
    return redirect(url_for('movimenti.list_movimenti'))


@bp.route('/webhook/stripe', methods=('POST',))
@csrf.exempt
def webhook_stripe():
    """ Notifica server-to-server da Stripe: nessuna sessione utente, quindi
    nessun token CSRF possibile. L'autenticazione della richiesta è la
    verifica della firma HMAC qui sotto, non un token di sessione. """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature', '')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        abort(400)

    if event['type'] == 'checkout.session.completed':
        conferma_pagamento('stripe', event['data']['object']['id'])

    elif event['type'] == 'checkout.session.expired':
        # Sessione creata (riga 'creato' in ricariche_esterne) ma mai
        # portata a termine dall'utente: niente da stornare, solo da
        # marcare come fallita per non lasciarla 'creato' per sempre.
        annulla_pagamento('stripe', event['data']['object']['id'],
                          'sessione scaduta senza pagamento')

    elif event['type'] == 'charge.refunded':
        charge = event['data']['object']
        if charge.get('refunded'):
            # Rimborso totale. Un rimborso parziale (refunded=False ma
            # amount_refunded>0) non viene stornato automaticamente: qui
            # arriverebbe solo l'importo cumulativo rimborsato finora, non
            # l'incremento, quindi andrebbe gestito a mano con una
            # rettifica su movimenti.
            sessioni = stripe.checkout.Session.list(
                payment_intent=charge['payment_intent'], limit=1)
            if sessioni.data:
                annulla_pagamento('stripe', sessioni.data[0].id,
                                  'rimborso Stripe')

    return '', 200


@bp.route('/riconciliazione')
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def riconciliazione():
    """ Pagina di controllo per le ricariche Stripe rimaste 'creato' oltre
    una finestra ragionevole: un webhook mai consegnato (URL irraggiungibile,
    secret sbagliato, downtime) lascerebbe altrimenti la riga silenziosamente
    disallineata da Stripe, senza nessun modo automatico di accorgersene.
    Lo stato mostrato per ogni riga è letto live dall'API Stripe (unica
    fonte autoritativa), non duplicato in locale. """
    dbi = get_db()
    dbi.execute("""
        SELECT ricariche_esterne.*, utenti.username
        FROM ricariche_esterne
        INNER JOIN utenti ON utenti.id = ricariche_esterne.id_utente
        WHERE ricariche_esterne.provider = 'stripe'
          AND ricariche_esterne.stato = 'creato'
          AND ricariche_esterne.creato_il < NOW() - INTERVAL '1 hour'
        ORDER BY ricariche_esterne.creato_il
        """)

    sospese = []
    for riga in dbi.fetchall():
        riga = dict(riga)
        try:
            sessione = stripe.checkout.Session.retrieve(riga['provider_ref'])
            riga['stato_stripe'] = sessione.status
            riga['pagamento_stripe'] = sessione.payment_status
        except stripe.error.StripeError:
            riga['stato_stripe'] = 'errore lettura da Stripe'
            riga['pagamento_stripe'] = None
        sospese.append(riga)

    return render_template('pagamenti/riconciliazione.html', sospese=sospese)


@bp.route('/riconciliazione/sincronizza', methods=('POST',))
@login_required
@is_ruolo(['moderatore', 'tesoriere'])
def riconciliazione_sincronizza():
    """ Rilegge lo stato autoritativo da Stripe per una singola riga sospesa
    e applica l'accredito o l'annullamento di conseguenza, invece di
    aspettare (o inseguire) un webhook che potrebbe non essere mai arrivato.
    Riusa conferma_pagamento()/annulla_pagamento(), quindi resta idempotente
    e coerente con quanto farebbe il webhook stesso. """
    provider_ref = request.form['provider_ref']
    sessione = stripe.checkout.Session.retrieve(provider_ref)

    if sessione.payment_status == 'paid':
        if conferma_pagamento('stripe', provider_ref):
            flash('Ricarica {0} accreditata manualmente'
                  .format(provider_ref), 'success')
        else:
            flash('Ricarica {0} già gestita o non tracciata'
                  .format(provider_ref), 'warning')
    elif sessione.status == 'expired':
        if annulla_pagamento('stripe', provider_ref,
                             'sessione scaduta (sincronizzazione manuale)'):
            flash('Ricarica {0} marcata come non riuscita'
                  .format(provider_ref), 'success')
        else:
            flash('Ricarica {0} già gestita o non tracciata'
                  .format(provider_ref), 'warning')
    else:
        flash('Ricarica {0} ancora in corso lato Stripe, nessuna azione'
              .format(provider_ref), 'warning')

    return redirect(url_for('pagamenti.riconciliazione'))


# --- Satispay -----------------------------------------------------------
#
# A differenza di Stripe non c'è un SDK ufficiale in Python: ogni richiesta
# va firmata a mano con lo schema a chiave RSA di Satispay (RSA-SHA256 sulle
# intestazioni (request-target)/host/date/digest, si veda
# https://developers.satispay.com/docs/authentication). SATISPAY_KEY_ID e
# SATISPAY_PRIVATE_KEY si ottengono una tantum scambiando il codice di
# attivazione (dashboard Satispay) e una chiave RSA generata da noi con
# POST /g_business/v1/authentication_keys — operazione di setup, non fa
# parte del flusso di pagamento.
#
# La callback S2S di Satispay (a differenza del webhook Stripe) è solo un
# trigger senza stato né firma garantita: contiene l'id del pagamento ma non
# l'esito, quindi va sempre seguita da una GET firmata su /payments/{id} per
# leggere lo stato autoritativo prima di accreditare (si veda
# https://developers.satispay.com/reference/callback-s2s).

SATISPAY_BASE_URL = os.environ.get(
    'SATISPAY_BASE_URL', 'https://authservices.satispay.com/g_business/v1')
SATISPAY_KEY_ID = os.environ.get('SATISPAY_KEY_ID')
SATISPAY_PRIVATE_KEY = os.environ.get('SATISPAY_PRIVATE_KEY', '').encode()


def _satispay_request(method, path, body=b''):
    """ Esegue una richiesta firmata verso l'API Satispay. `path` è relativo
    a SATISPAY_BASE_URL (es. '/payments'); il (request-target) firmato deve
    però riportare il path completo così come appare nella richiesta HTTP
    (es. '/g_business/v1/payments'), non solo la parte passata qui. """
    full_url = SATISPAY_BASE_URL + path
    url_parts = urlsplit(full_url)
    request_target = url_parts.path
    if url_parts.query:
        request_target += '?' + url_parts.query
    host = url_parts.netloc
    date = formatdate(usegmt=True)
    digest = 'SHA-256=' + base64.b64encode(
        hashlib.sha256(body).digest()).decode()

    signing_string = '\n'.join([
        '(request-target): {0} {1}'.format(method.lower(), request_target),
        'host: {0}'.format(host),
        'date: {0}'.format(date),
        'digest: {0}'.format(digest),
    ])
    private_key = serialization.load_pem_private_key(
        SATISPAY_PRIVATE_KEY, password=None)
    signature = base64.b64encode(private_key.sign(
        signing_string.encode(), padding.PKCS1v15(), hashes.SHA256()
    )).decode()
    authorization = (
        'Signature keyId="{0}", algorithm="rsa-sha256", '
        'headers="(request-target) host date digest", signature="{1}"'
    ).format(SATISPAY_KEY_ID, signature)

    response = requests.request(
        method, full_url, data=body, headers={
            'Host': host,
            'Date': date,
            'Digest': digest,
            'Authorization': authorization,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }, timeout=10)
    response.raise_for_status()
    return response.json()


@bp.route('/ricarica/satispay', methods=('POST',))
@login_required
def ricarica_satispay():
    """ Analogo a ricarica() ma per Satispay: crea il pagamento lato Satispay
    e reindirizza l'utente alla pagina (ospitata da Satispay) per
    confermarlo dall'app. """
    if not (SATISPAY_KEY_ID and SATISPAY_PRIVATE_KEY):
        # Raggiunta direttamente (bottone nascosto da SATISPAY_ABILITATO)
        # prima che le chiavi siano configurate.
        flash('Pagamento con Satispay non ancora disponibile.', 'warning')
        return render_template('pagamenti/ricarica.html')

    try:
        importo = float(request.form['importo'])
    except (KeyError, ValueError):
        flash('Importo non valido', 'warning')
        return render_template('pagamenti/ricarica.html')

    if not IMPORTO_MINIMO <= importo <= IMPORTO_MASSIMO:
        flash('Importo non valido: deve essere tra {0} e {1} euro'
              .format(IMPORTO_MINIMO, IMPORTO_MASSIMO), 'warning')
        return render_template('pagamenti/ricarica.html')

    callback_url = (url_for('pagamenti.webhook_satispay', _external=True)
                     + '?payment_id={uuid}')
    body = json.dumps({
        'flow': 'MATCH_CODE',
        'amount_unit': round(importo * 100),
        'currency': 'EUR',
        'callback_url': callback_url,
        'redirect_url': url_for('pagamenti.ricarica_completata',
                                 _external=True),
    }).encode()
    pagamento = _satispay_request('POST', '/payments', body)

    registra_pagamento_creato('satispay', pagamento['id'], g.user['id'],
                               importo)

    return redirect(pagamento['redirect_url'], code=303)


@bp.route('/webhook/satispay', methods=('GET',))
@csrf.exempt
def webhook_satispay():
    """ Trigger S2S da Satispay: nessuna sessione utente (nessun token CSRF
    possibile, come per il webhook Stripe) e nessuno stato nel payload, solo
    l'id del pagamento — lo stato va sempre riletto da Satispay stessa. """
    payment_id = request.args.get('payment_id')
    if not payment_id:
        abort(400)

    try:
        pagamento = _satispay_request(
            'GET', '/payments/{0}'.format(payment_id))
    except requests.RequestException:
        # payment_id sconosciuto/non valido o Satispay momentaneamente
        # irraggiungibile: nessun accredito, ma la richiesta va comunque
        # chiusa senza un 500 (nessuno stack trace utile per un chiamante
        # S2S, e Satispay potrebbe ripetere la callback più tardi).
        return '', 200

    if pagamento.get('status') == 'ACCEPTED':
        conferma_pagamento('satispay', payment_id)

    return '', 200
