""" Istanze condivise di estensioni Flask, separate da __init__.py per poter
essere importate (es. per @csrf.exempt) senza creare un ciclo di import con
create_app(). """
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
