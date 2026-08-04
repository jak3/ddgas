"""INIT Flask"""

import os
from urllib.parse import urlparse

from datetime import datetime

import click
import yaml
from flask import Flask, render_template, g, redirect, url_for
from flask_wtf.csrf import generate_csrf
from markupsafe import Markup
from werkzeug.security import generate_password_hash

from delek.extensions import csrf
from delek.controller.db import get_db, init_app
from delek.controller.auth import bp as auth_bp
from delek.controller.istruzioni import bp as istruzioni_bp
from delek.controller.listini import bp as listini_bp
from delek.controller.movimenti import bp as movimenti_bp, get_totale_utente
from delek.controller.ordini import bp as ordini_bp
from delek.controller.pagamenti import bp as pagamenti_bp
from delek.controller.presidi import bp as presidi_bp
from delek.controller.produttori import bp as produttori_bp
from delek.controller.ruoli import bp as ruoli_bp
from delek.controller.stampa import bp as stampa_bp


def forbidden(e):
    return render_template('error/403.html'), 403


def page_not_found(e):
    return render_template('error/404.html'), 404


def internal_error(e):
    return render_template('error/500.html'), 500


def bad_request(e):
    return render_template('error/400.html'), 400


def load_associazione_config(app):
    """Carica i dati pubblici dell'associazione (branding, contatti,
    regole) da config/associazione.yaml e li rende disponibili in
    app.config['ASSOCIAZIONE'] e come variabile 'associazione' in ogni
    template."""
    path = os.path.join(app.root_path, '..', 'config', 'associazione.yaml')
    with open(path, encoding='utf-8') as f:
        app.config['ASSOCIAZIONE'] = yaml.safe_load(f)

    @app.context_processor
    def inject_associazione():
        return {'associazione': app.config['ASSOCIAZIONE']}


def create_app(local=False):
    """INIT App"""

    app = Flask(__name__, instance_relative_config=True)
    app.register_error_handler(400, bad_request)
    app.register_error_handler(403, forbidden)
    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, internal_error)
    load_associazione_config(app)

    csrf.init_app(app)

    @app.template_global()
    def csrf_field():
        """Da usare in ogni <form method="post">: {{ csrf_field() }}"""
        return Markup(
            '<input type="hidden" name="csrf_token" value="{}">'.format(generate_csrf())
        )

    SOGLIA_SALDO_BASSO = 20

    # Finché STRIPE_SECRET_KEY non è configurata, il blueprint 'pagamenti'
    # non viene registrato: 'pagamenti_abilitati' permette a base.html di
    # non generare link a url_for('pagamenti.*'), che altrimenti farebbero
    # fallire ogni pagina con un BuildError.
    pagamenti_abilitati = bool(os.environ.get('STRIPE_SECRET_KEY'))
    app.config['PAGAMENTI_ABILITATI'] = pagamenti_abilitati

    # Satispay condivide il blueprint 'pagamenti' con Stripe, ma può essere
    # pronto in un momento diverso: questo flag separato evita di esporre il
    # bottone "Paga con Satispay" prima che SATISPAY_KEY_ID/PRIVATE_KEY siano
    # configurate (altrimenti cliccarlo darebbe un errore).
    app.config['SATISPAY_ABILITATO'] = bool(
        os.environ.get('SATISPAY_KEY_ID') and os.environ.get('SATISPAY_PRIVATE_KEY')
    )

    @app.context_processor
    def inject_saldo_basso():
        """Espone 'saldo_basso' ad ogni template quando l'utente loggato
        ha un credito sotto SOGLIA_SALDO_BASSO, per l'avviso in base.html"""
        if pagamenti_abilitati and g.get('user'):
            saldo = float(get_totale_utente(g.user['id']) or 0)
            if saldo < SOGLIA_SALDO_BASSO:
                return {'saldo_basso': saldo}
        return {'saldo_basso': None}

    @app.context_processor
    def inject_anno_corrente():
        """Per il copyright nel footer di base.html."""
        return {'anno_corrente': datetime.now().year}

    if not local:
        url = urlparse(os.environ.get('DATABASE_URL'))
        dbparams = "dbname=%s user=%s password=%s host=%s sslmode=%s" % (
            url.path[1:],
            url.username,
            url.password,
            url.hostname,
            'require',
        )
    else:
        # DELEK_LOCAL_DB permette ai test di puntare a un DB usa-e-getta
        # (es. delek_test) senza toccare il delek di sviluppo. DELEK_DB_HOST
        # di default resta 127.0.0.1 (sviluppo locale nativo); in Docker
        # Compose l'app deve invece raggiungere il servizio 'db' per nome.
        dbparams = "dbname=%s host=%s" % (
            os.environ.get('DELEK_LOCAL_DB', 'delek'),
            os.environ.get('DELEK_DB_HOST', '127.0.0.1'),
        )

    app.config.from_mapping(
        DB_PARAMS=dbparams,
        SENDGRID_API_KEY=os.environ.get('SENDGRID_API_KEY'),
        SENDGRID_FROM_EMAIL=os.environ.get('SENDGRID_FROM_EMAIL'),
        SECRET_KEY=os.environ.get('SECRET_KEY'),
    )

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route('/')
    def index():
        if g.user:
            return redirect(url_for('ordini.list_ordini'))
        return render_template('/chi-siamo.html')

    @app.route('/contatti')
    def contatti():
        return render_template('/contatti.html')

    @app.route('/regolamento')
    def regolamento():
        return render_template('/regolamento.html')

    @app.template_filter()
    def data(date):
        """Usato per <p>"""
        return date.strftime("%d / %m / %Y")

    @app.template_filter()
    def data_input(dtime):
        """Usato per <input>"""
        if isinstance(dtime, str):
            dtime = datetime.fromisoformat(dtime)
        return dtime.strftime("%Y-%m-%d")

    @app.template_filter()
    def data_it(dtime):
        """Usato per stampare una data nel formato italiano"""
        if isinstance(dtime, str):
            dtime = datetime.fromisoformat(dtime)
        return dtime.strftime("%d / %m / %Y")

    init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(istruzioni_bp)
    app.register_blueprint(listini_bp)
    app.register_blueprint(movimenti_bp)
    app.register_blueprint(ordini_bp)
    if pagamenti_abilitati:
        app.register_blueprint(pagamenti_bp)
    app.register_blueprint(presidi_bp)
    app.register_blueprint(produttori_bp)
    app.register_blueprint(ruoli_bp)
    app.register_blueprint(stampa_bp)
    app.add_url_rule('/', endpoint='index')

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True)
    @click.option('--email', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(username, email, password):
        """Crea il primo utente con ruolo moderatore per una nuova
        istanza (già attivo, non passa dal flusso di attivazione email).
        Utile subito dopo aver applicato schema.sql/bootstrap.sql, quando
        non esiste ancora nessuno con i permessi per assegnare ruoli da
        interfaccia."""
        dbi = get_db()

        dbi.execute('SELECT id FROM utenti WHERE username = %s', (username,))
        if dbi.fetchone():
            click.echo("Utente '{0}' già esistente.".format(username))
            return

        dbi.execute(
            """
            INSERT INTO utenti (username, password, email, attivo)
            VALUES (%s, %s, %s, TRUE) RETURNING id
            """,
            (username, generate_password_hash(password), email),
        )
        id_utente = dbi.fetchone()['id']

        dbi.execute("SELECT id FROM ruoli WHERE ruolo = 'moderatore'")
        ruolo = dbi.fetchone()
        if ruolo:
            id_ruolo = ruolo['id']
        else:
            dbi.execute("""
                INSERT INTO ruoli (ruolo, descrizione) VALUES ('moderatore',
                    'Aggiunge produttori, assegna referenti, gestisce i membri')
                RETURNING id
                """)
            id_ruolo = dbi.fetchone()['id']

        dbi.execute(
            'INSERT INTO arruolati (id_ruolo, id_utente) VALUES (%s, %s)',
            (id_ruolo, id_utente),
        )

        click.echo("Utente '{0}' creato con ruolo moderatore.".format(username))

    return app
