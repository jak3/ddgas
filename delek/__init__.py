""" INIT Flask """
import os
from urllib.parse import urlparse

from datetime import datetime

import yaml
from flask import (Flask, render_template, g, redirect, url_for)

from delek.controller.db import init_app
from delek.controller.auth import bp as auth_bp
from delek.controller.istruzioni import bp as istruzioni_bp
from delek.controller.listini import bp as listini_bp
from delek.controller.movimenti import bp as movimenti_bp
from delek.controller.ordini import bp as ordini_bp
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


def load_associazione_config(app):
    """ Carica i dati pubblici dell'associazione (branding, contatti,
    regole) da config/associazione.yaml e li rende disponibili in
    app.config['ASSOCIAZIONE'] e come variabile 'associazione' in ogni
    template. """
    path = os.path.join(app.root_path, '..', 'config', 'associazione.yaml')
    with open(path, encoding='utf-8') as f:
        app.config['ASSOCIAZIONE'] = yaml.safe_load(f)

    @app.context_processor
    def inject_associazione():
        return {'associazione': app.config['ASSOCIAZIONE']}


def create_app(local=False):
    """ INIT App """

    app = Flask(__name__, instance_relative_config=True)
    app.register_error_handler(403, forbidden)
    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, internal_error)
    load_associazione_config(app)

    if not local:
        url = urlparse(os.environ.get('DATABASE_URL'))
        dbparams = "dbname=%s user=%s password=%s host=%s sslmode=%s" % (
            url.path[1:], url.username, url.password, url.hostname,
            'require')
    else:
        dbparams = "dbname=%s host=%s" % ('delek', '127.0.0.1')

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
        """ Usato per <p> """
        return date.strftime("%d / %m / %Y")

    @app.template_filter()
    def data_input(dtime):
        """ Usato per <input> """
        if isinstance(dtime, str):
            dtime = datetime.fromisoformat(dtime)
        return dtime.strftime("%Y-%m-%d")

    @app.template_filter()
    def data_it(dtime):
        """ Usato per stampare una data nel formato italiano """
        if isinstance(dtime, str):
            dtime = datetime.fromisoformat(dtime)
        return dtime.strftime("%d / %m / %Y")

    init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(istruzioni_bp)
    app.register_blueprint(listini_bp)
    app.register_blueprint(movimenti_bp)
    app.register_blueprint(ordini_bp)
    app.register_blueprint(presidi_bp)
    app.register_blueprint(produttori_bp)
    app.register_blueprint(ruoli_bp)
    app.register_blueprint(stampa_bp)
    app.add_url_rule('/', endpoint='index')

    return app
