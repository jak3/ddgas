""" Classi per la convalida dei dati """

from re import fullmatch
from collections import namedtuple
from datetime import datetime

CF = r'(?:\w{11}|\w{16})'
DECIMAL_MAX_TWO_PLACES = r'\d+(\.\d{1,2})?'
DECIMAL_MAX_TWO_PLACES_SIGNED = r'-?' + DECIMAL_MAX_TWO_PLACES
EMAIL = r'([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})'
ID = r'[1-9][0-9]*'
INTEGER_POSITIVE = r'[0-9]+'
MULTI_LINE_STRING = r'(.+\n?)+'
PHONE = r'(\+?[0-9]{6,12})?'
SINGLE_LINE_STRING = r'.*'
URL = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'
VARCHAR_40 = r'[a-z]{,40}'
ZERO_OR_ONE = r'(0|1)'

ChecknError = namedtuple('ChecknError',
                            ['regex', 'error_msg', 'could_be_empty'])
def create_checknerror(regex, error_msg, could_be_empty=True ):
    """ Create a ChecknError type with default NOT empty regex """
    return ChecknError(regex, error_msg, could_be_empty)

CeAttivo = {'attivo': create_checknerror( ZERO_OR_ONE, 'Attivo non conforme')}
CeDescrizione = {'descrizione':
                    create_checknerror( MULTI_LINE_STRING,
                                        'Descrizione non conforme')}
CeEmail = {'email': create_checknerror( EMAIL, 'Email non conforme')}

CeId = {'id': create_checknerror( ID, 'Id non conforme')}

def gen_ceid(id_name, error_msg, could_be_empty=True) -> dict:
    """ Genera un CeId parametrizzato con nome e messaggio di errore """
    return { id_name: create_checknerror( ID, error_msg, could_be_empty )}

def gen_cenome(regex, could_be_empty=True):
    """ Genera un CeNome con regex di matching come argomento """
    return { 'nome': create_checknerror(regex,
                                        'Nome non conforme',
                                        could_be_empty) }

CeIdProduttoreRequired = gen_ceid('id_produttore',
                      'Id Produttore non conforme', could_be_empty=False)
CeIdUtenteRequired = gen_ceid('id_utente',
                      'Id Utente non conforme', could_be_empty=False)

def gen_categoria(name, could_be_empty=True):
    """ Genera una CeCategoria con nome alternavivo """
    return name, create_checknerror(SINGLE_LINE_STRING,
                                    'Categoria non conforme',
                                    could_be_empty)

CeNota = {'nota': create_checknerror( MULTI_LINE_STRING, 'Nota non conforme' )}
CeTelefono = {'telefono':
                create_checknerror( PHONE, 'Numero di telefono non conforme')}

def check_valid_date(date_text) -> dict:
    """ Controllo formato data """
    try:
        datetime.fromisoformat(date_text)
    except ValueError:
        return { 'error_msg': 'Formato data non conforme' }

    return {}

def _check(checks, inputs) -> dict:

    for (what, checker) in checks.items():
        check_object = inputs.get(what)

        if isinstance(check_object, list):
            for (idx, input_value) in enumerate(check_object):
                if not fullmatch(checker.regex, input_value):
                    return {
                            'error_msg': checker.error_msg,
                            'id': str(idx),
                            'input_value': input_value,
                        }
        else:
            check_object = check_object or ''
            if not isinstance(check_object, str):
                # Alcuni chiamanti (es. giroconto_utente) costruiscono
                # 'inputs' iniettando valori non-stringa (es. tipologia
                # intera): fullmatch() richiede str, non deve esplodere.
                check_object = str(check_object)
            if not checker.could_be_empty and not check_object:
                return {
                        'error_msg':
                                "Il campo '" + what + "' non può essere vuoto",
                        'id': '0',
                        'input_value': check_object
                }
            if check_object and not fullmatch(checker.regex, check_object):
                return {
                        'error_msg': checker.error_msg,
                        'id': '0',
                        'input_value': check_object,
                }

    return {}

def check_inputs_listino (inputs):
    """ :inputs è una dict dei valori in input"""
    checks = gen_ceid('id_prodotto', 'Id prodotto non conforme') | {

        'descrizione_prodotto': create_checknerror(
            SINGLE_LINE_STRING,
            'Descrizione del Prodotto richiesta',
            could_be_empty=False
        ),

        'dettaglio_qta': create_checknerror(
            SINGLE_LINE_STRING,
            'Dettaglio quantità non conforme',
        ),

        'disponibile': create_checknerror(
            ZERO_OR_ONE,
            'Disponibilità prodotto non valida',
        ),

        'prezzo': create_checknerror(
            DECIMAL_MAX_TWO_PLACES,
            'Prezzo del prodotto non conforme',
            could_be_empty=False
        ),

        'n_min_colli': create_checknerror(
            INTEGER_POSITIVE,
            'Numero minimo colli prodotto non conforme',
        ),

        'n_max_colli': create_checknerror(
            INTEGER_POSITIVE,
            'Numero massimo colli prodotto non conforme',
        ),

        'colli_disponibili': create_checknerror(
            INTEGER_POSITIVE,
            'Numero colli disponibili prodotto non conforme',
        ),
    } | CeNota | dict([gen_categoria(name) for name in ['categoria',
                                                        'old_categoria',
                                                        'new_categoria']])

    return _check(checks, inputs)

def check_inputs_utente(inputs):
    """ :inputs form per utente """
    checks = CeId | {

        'username': create_checknerror(
            SINGLE_LINE_STRING,
            'Username non conforme o non inserito',
            could_be_empty=False
        ),

        'password': create_checknerror(
            SINGLE_LINE_STRING,
            'Password non conforme',
            could_be_empty=False
        ),

        'cognome': create_checknerror(
            SINGLE_LINE_STRING,
            'Cognome non conforme'
        ),

        'cf': create_checknerror(
            CF,
            'Codice Fiscale non conforme'
        ),

    } | CeEmail | CeTelefono | gen_cenome(SINGLE_LINE_STRING) | CeAttivo

    return _check(checks, inputs)

def check_inputs_produttore(inputs):
    """ :inputs form per utente """
    checks = ( gen_ceid('id_utente', 'Id Utente Referente non conforme') |

               CeId | gen_cenome(SINGLE_LINE_STRING) | CeEmail |

               CeTelefono | { 'website': create_checknerror(
                    URL,
                    'Pagina Web non valida'
                ),

                'mask_mesi_consegna': create_checknerror(
                    r'(0|1){12}',
                    'Maschera per mesi di consegna non conforme al formato'
                    ' a 12 bit (es: 101010101010)'
                ),

                'prodotto_principale': create_checknerror(
                    SINGLE_LINE_STRING,
                    'Prodotto Principale non conforme'
                ),
                'descrizione': create_checknerror(
                    MULTI_LINE_STRING,
                    'Descrizione non conforme'
                )
            } | CeAttivo )

    return _check(checks, inputs)

def check_inputs_movimento(inputs):
    """ :inputs form per movimento """
    inputs = dict(inputs)
    error = {}

    if 'effettuato_il' in inputs.keys():
        error |= check_valid_date(inputs.get('effettuato_il'))
        inputs.pop('effettuato_il')

    if error:
        return error

    checks = { 'per_id_utente': create_checknerror( ID,
                    'Id utente di riferimento non conforme',
                ),

                'verso_id': create_checknerror( ID,
                    'Id utente verso cui effettuare il movimento non conforme'
                ),

                # '0' = applicativo
                'gestore' : create_checknerror( INTEGER_POSITIVE,
                    'Gestore del movimento non conforme',
                ),

                'tipologia': create_checknerror( '(1|2|3|4|5|6|7|8)',
                    'Tipologia movimento non prevista.'
                    ' Disponibile versamento:1, prelievo:2,'
                    ' giroconto:3, acquisto:4, rettifica:5,'
                    ' aggiustamento: 6, spese CC: 7, spese varie: 8',
                ),

                'importo': create_checknerror( DECIMAL_MAX_TWO_PLACES_SIGNED,
                    'Importo del movimento non conforme',
                    could_be_empty=False
                ),

                'descrizione': create_checknerror(
                    MULTI_LINE_STRING,
                    'Descrizione non conforme',
                    could_be_empty=False
                )
    }

    return _check(checks, inputs)

def check_inputs_ordine(inputs):
    """ Check per inserimento nuovo ordine singolo utente """
    checks = gen_ceid('id_prodotto',
                      'Id prodotto non conforme', could_be_empty=False) | {
                'prezzo': create_checknerror(
                    DECIMAL_MAX_TWO_PLACES,
                    'Prezzo del prodotto non conforme',
                    could_be_empty=False
                ),
                'colli_richiesti': create_checknerror(
                    INTEGER_POSITIVE,
                    'Numero di Colli Richiesti non conforme',
                ),
                'specifica': create_checknerror(
                    SINGLE_LINE_STRING,
                    'Specifica del prodotto non conforme'
                )}
    return _check(checks, inputs)

def check_inputs_dettagli_ordine(inputs):
    """ Check per creazione dettaglio ordine per produttore """
    inputs = dict(inputs)
    error = {}

    if inputs.get('scadenza'):
        error |= check_valid_date(inputs.get('scadenza'))
        # Non necessito di controllarli ancora con _check
        inputs.pop('scadenza')

    if inputs.get('consegna'):
        error |= check_valid_date(inputs.get('consegna'))
        inputs.pop('consegna')

    if error:
        return error

    checks = CeIdProduttoreRequired | {

                'minimo_ordine': create_checknerror(
                    DECIMAL_MAX_TWO_PLACES,
                    'Minimo d\'ordine non conforme'

                )} | CeNota

    return _check(checks, inputs)

def check_inputs_rettifiche(inputs):
    """ Check per la creazione delle rettifiche post ordine """
    checks = CeIdUtenteRequired | {
            'per_id_utente': create_checknerror( ID,
                'Id Utente non conforme',
                ),
            'importo': create_checknerror( DECIMAL_MAX_TWO_PLACES,
                'Importo non conforme, un acquisto non può essere negativo',
                ),
            'importo_rettifica': create_checknerror(
                DECIMAL_MAX_TWO_PLACES,
                'Importo rettifica non conforme'
                ),
            'motivazione': create_checknerror(
                MULTI_LINE_STRING,
                'Motivazione rettifica non conforme'
                ),
            'rimuovi': create_checknerror(
                ID,
                'Rimuovi non conforme'
                ),
            'pre-conferma': create_checknerror(
                SINGLE_LINE_STRING,
                'Conferma non conforme'
                ),
            'conferma': create_checknerror(
                SINGLE_LINE_STRING,
                'Conferma non conforme'
                ),
            'extra_id_utente': create_checknerror(
                ID,
                'ID Utente Extra non conforme'
                ),
            'extra_utente': create_checknerror(
                SINGLE_LINE_STRING,
                'Utente Extra non conforme'
                ),
            'extra_importo': create_checknerror(
                DECIMAL_MAX_TWO_PLACES,
                'Importo Extra non conforme, non può essere negativo'
                ),
            'extra_descrizione': create_checknerror(
                MULTI_LINE_STRING,
                'Extra descrizione non conforme'
                ),
            } | CeDescrizione


    return _check(checks, inputs)

def check_inputs_ruolo(inputs):
    """ Check per la creazione del ruolo """
    checks = { 'descrizione': create_checknerror( MULTI_LINE_STRING,
                    'Descrizione non conforme',
                    could_be_empty=False),

                'nome': create_checknerror( VARCHAR_40,
                    'Nome del ruolo non conforme',
                    could_be_empty=False)
             }

    return _check(checks, inputs)

def check_inputs_isid(inputs):
    """ Check se inputs risulta un ID valido """
    checks = CeId

    return _check(checks, inputs)

def check_inputs_quota(inputs):
    """ Check se inputs risulta essere una quota/prezzo valido """

    checks = { 'quota': create_checknerror(DECIMAL_MAX_TWO_PLACES,
                'Quota tessera annuale non conforme',
                could_be_empty=False) } | CeId

    return _check(checks, inputs)

def check_inputs_smemo(inputs):
    """ Check username ed email per reset password """

    checks = { 'username': create_checknerror(
        SINGLE_LINE_STRING,
        'Username non conforme o non inserito',
        could_be_empty=False
        ) } | CeEmail

    return _check(checks, inputs)

def check_aggiusta_ordine_chiuso(inputs):
    """ Check per aggiustare ordine chiuso """

    inputs = dict(inputs)
    error = {}

    if inputs.get('data'):
        error |= check_valid_date(inputs.get('data'))
        inputs.pop('data')
    if error:
        return error

    checks = { 'nuovo_totale': create_checknerror(
                    DECIMAL_MAX_TWO_PLACES,
                    'Nuovo totale non conforme',
                    could_be_empty=False
                    ) } | CeIdProduttoreRequired | CeDescrizione

    return _check(checks, inputs)
