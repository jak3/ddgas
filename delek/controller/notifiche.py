"""Iscrizioni ai promemoria email di scadenza ordine e invio del promemoria"""

from flask import Blueprint, current_app, g, redirect, url_for
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from delek.controller.auth import login_required
from delek.controller.db import get_db

bp = Blueprint('notifiche', __name__, url_prefix='/notifiche')


@bp.route('/produttore/<int:id_produttore>/iscriviti', methods=('POST',))
@login_required
def produttore_iscriviti(id_produttore):
    """Iscrizione permanente: avvisami per ogni futuro ordine di questo
    produttore, non solo per quello attualmente aperto"""
    get_db().execute(
        """ INSERT INTO notifiche_produttore (id_utente, id_produttore)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING """,
        (g.user['id'], id_produttore),
    )
    return redirect(url_for('ordini.list_ordini'))


@bp.route('/produttore/<int:id_produttore>/disiscriviti', methods=('POST',))
@login_required
def produttore_disiscriviti(id_produttore):
    get_db().execute(
        'DELETE FROM notifiche_produttore WHERE id_utente = %s AND id_produttore = %s',
        (g.user['id'], id_produttore),
    )
    return redirect(url_for('ordini.list_ordini'))


@bp.route('/ordine/<int:id_dettaglio_ordine>/iscriviti', methods=('POST',))
@login_required
def ordine_iscriviti(id_dettaglio_ordine):
    """Iscrizione una tantum: avvisami solo per l'ordine attualmente aperto"""
    get_db().execute(
        """ INSERT INTO notifiche_ordine (id_utente, id_dettaglio_ordine)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING """,
        (g.user['id'], id_dettaglio_ordine),
    )
    return redirect(url_for('ordini.list_ordini'))


@bp.route('/ordine/<int:id_dettaglio_ordine>/disiscriviti', methods=('POST',))
@login_required
def ordine_disiscriviti(id_dettaglio_ordine):
    get_db().execute(
        'DELETE FROM notifiche_ordine'
        ' WHERE id_utente = %s AND id_dettaglio_ordine = %s',
        (g.user['id'], id_dettaglio_ordine),
    )
    return redirect(url_for('ordini.list_ordini'))


def get_ordini_da_notificare():
    """Ordini che scadono entro le prossime 24 ore e non hanno ancora
    ricevuto il promemoria. Finestra aperta (<=), non un BETWEEN stretto:
    un ordine creato a ridosso della scadenza o un run schedulato saltato
    vengono comunque intercettati dal run successivo."""
    dbi = get_db()
    dbi.execute(
        """
        SELECT dettagli_ordini.id AS id_dettaglio_ordine, id_produttore,
                scadenza, produttori.nome AS nome_produttore
        FROM dettagli_ordini INNER JOIN produttori
            ON produttori.id = id_produttore
        WHERE scadenza >= now() AND scadenza <= now() + interval '24 hours'
              AND NOT promemoria_inviato
        """
    )
    return dbi.fetchall()


def get_destinatari(id_produttore, id_dettaglio_ordine):
    """Referenti del produttore (sempre) più gli iscritti volontari
    (permanenti per il produttore, o una tantum per questo ordine).
    Deduplicato su email, non su id_utente, così due account con la
    stessa email non ricevono due copie."""
    dbi = get_db()
    dbi.execute(
        """
        SELECT DISTINCT email FROM utenti
        INNER JOIN referenze ON referenze.id_utente = utenti.id
        WHERE referenze.id_produttore = %(id_produttore)s AND email IS NOT NULL
        UNION
        SELECT DISTINCT email FROM utenti
        INNER JOIN notifiche_produttore
            ON notifiche_produttore.id_utente = utenti.id
        WHERE notifiche_produttore.id_produttore = %(id_produttore)s
              AND email IS NOT NULL
        UNION
        SELECT DISTINCT email FROM utenti
        INNER JOIN notifiche_ordine ON notifiche_ordine.id_utente = utenti.id
        WHERE notifiche_ordine.id_dettaglio_ordine = %(id_dettaglio_ordine)s
              AND email IS NOT NULL
        """,
        {'id_produttore': id_produttore, 'id_dettaglio_ordine': id_dettaglio_ordine},
    )
    return [row['email'] for row in dbi.fetchall()]


def invia_promemoria(ordine, destinatari):
    """Un invio SendGrid per destinatario (non un unico messaggio
    multi-to_emails, per non esporre la lista a tutti). Un invio fallito
    non blocca gli altri destinatari dello stesso ordine."""
    client = SendGridAPIClient(current_app.config['SENDGRID_API_KEY'])
    inviate = 0
    for email in destinatari:
        msg = Mail(
            from_email=current_app.config['SENDGRID_FROM_EMAIL'],
            to_emails=email,
            subject='Ordine {0} in scadenza'.format(ordine['nome_produttore']),
            plain_text_content=''.join(
                [
                    "L'ordine di {0} chiude il {1}.\n".format(
                        ordine['nome_produttore'],
                        ordine['scadenza'].strftime('%d/%m/%Y %H:%M'),
                    ),
                    'Se non hai ancora ordinato, fai in tempo.',
                ]
            ),
        )
        try:
            client.send(msg)
            inviate += 1
        except Exception:
            current_app.logger.exception(
                "Invio promemoria fallito per %s (ordine produttore id=%s)",
                email,
                ordine['id_produttore'],
            )
    return inviate


def esegui_promemoria_ordini():
    """Per ogni ordine dovuto: calcola i destinatari, invia, e marca come
    processato solo se l'invio non solleva eccezione (send-then-mark: se
    SendGrid fallisce del tutto per un ordine, il giorno dopo viene
    ritentato)."""
    dbi = get_db()
    ordini_processati = 0
    email_inviate = 0

    for ordine in get_ordini_da_notificare():
        destinatari = get_destinatari(
            ordine['id_produttore'], ordine['id_dettaglio_ordine']
        )
        try:
            if destinatari:
                email_inviate += invia_promemoria(ordine, destinatari)
            dbi.execute(
                'UPDATE dettagli_ordini SET promemoria_inviato = TRUE WHERE id = %s',
                (ordine['id_dettaglio_ordine'],),
            )
            ordini_processati += 1
        except Exception:
            current_app.logger.exception(
                'Promemoria non completato per ordine produttore id=%s',
                ordine['id_produttore'],
            )

    return 'Promemoria: {0} ordini processati, {1} email inviate'.format(
        ordini_processati, email_inviate
    )
