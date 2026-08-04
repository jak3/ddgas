""" Fuso orario per le colonne timestamptz (scadenza, consegna, ecc).

Centralizzato qui invece che sparso: il server puo' girare in un fuso
diverso da quello dei gasisti (es. UTC su Heroku), quindi 'adesso' e le
date inserite da form vanno sempre ancorate esplicitamente a Europe/Rome
prima di confrontarle o salvarle. Nessuna dipendenza da altri controller,
per evitare import circolari.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo('Europe/Rome')


def adesso():
    """ Sostituisce datetime.now()/datetime.today(): il server puo' girare
    in un fuso diverso da quello dei gasisti, 'adesso' deve restare
    sempre quello percepito da loro. """
    return datetime.now(FUSO)


def da_form(value):
    """ Un valore di un <input type="datetime-local"> (stringa ISO senza
    offset) rappresenta sempre un orario Europe/Rome: gli si assegna
    esplicitamente quel fuso. Se il valore ha gia' un offset (es.
    riproposto da un <option> gia' serializzato dal DB) viene lasciato
    invariato, per non reinterpretare un istante gia' corretto. """
    dtime = datetime.fromisoformat(value) if isinstance(value, str) else value
    if dtime.tzinfo is None:
        dtime = dtime.replace(tzinfo=FUSO)
    return dtime
