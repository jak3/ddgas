""" Istruzioni """
from flask import (
    Blueprint, render_template
)

bp = Blueprint('istruzioni', __name__, url_prefix='/istruzioni')


@bp.route('/acquisto')
def acquisto():
    """ pagina statica con le istruzioni per gli acquisti """
    return render_template('istruzioni/acquisto.html')


@bp.route('/list')
def list_tutorial():
    """ pagina statica con i video tutorial """
    return render_template('istruzioni/list.html')
