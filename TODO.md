# TODO — Sicurezza e logica (delek/)

Nota di lavoro dalla revisione di sicurezza/logica del 2026-07-17 su `delek/`.
Elenco di quanto già sistemato e di quanto resta da valutare.

## Fatto

1. **Cancellazione movimento via GET, senza conferma reale** — `movimenti.py`
   `delete()` era una route GET priva di `methods=`, cancellabile da un
   prefetch del browser, un bot di anteprima link o "apri in nuova scheda"
   (il `confirm()` era legato solo a `onclick`, mai eseguito in questi casi).
   → Route convertita a `POST`, link convertito in form, aggiunto flash di
   conferma. Probabile causa del movimento tesseramento sparito nel DB.

2. **Bypass di login tramite `effettua_tesseramento`** — la route non aveva
   `@login_required` e prendeva `id_utente` dall'URL: chiunque poteva forzare
   il pagamento tesseramento di un altro utente e ottenere una sessione
   autenticata come quell'utente, senza conoscerne la password.
   → `id_utente` non arriva più dall'URL ma da `session['pending_tesseramento']`,
   valorizzata solo dopo una verifica riuscita di username/password in `login()`.

3. **Escalation di privilegi a moderatore** — `gestione_permessi` (pagina di
   assegnazione ruoli/referenze) non aveva nessun controllo di ruolo, solo
   `@login_required`: qualsiasi utente autenticato poteva assegnarsi il ruolo
   `moderatore`. Anche `remove_role`/`remove_reference` erano GET senza conferma.
   → Aggiunto `@is_ruolo(['moderatore'])` a `gestione_permessi`; le due
   funzioni di rimozione sono ora POST con conferma, e la query f-string di
   `remove_role` è stata parametrizzata.

4. **SQL injection in creazione ordine** — `ordini.py` `create()` eseguiva
   `SELECT * FROM listino_{id_produttore}` (interpolato via `.format()`)
   *prima* che la validazione di `id_produttore` venisse controllata.
   → La query dinamica ora gira solo dentro `if not error:`, con cast
   esplicito a `int()`.

5. **SQL injection + IDOR in `movimenti._list_movimenti`** — gli errori di
   validazione di `da_data`/`a_data`/`id_utente`/`tipologia` si
   sovrascrivevano a vicenda (`error = check(...)` invece di accumularsi),
   permettendo di far eseguire un filtro data non validato aggiungendo un
   altro campo valido nella stessa POST. In più, `list_movimenti()` (pagina
   "i miei movimenti", nessun controllo di ruolo) permetteva di vedere i
   movimenti di un altro utente passando `id_utente` nel form.
   → Errori ora accumulati (`error = error or check(...)`); aggiunto flag
   `own_only` per impedire l'override di `id_utente` dalla pagina personale.

6. **Eccezioni JWT non gestite in `reset_password`** — veniva catturato solo
   `jwt.ExpiredSignatureError`; un token mancante/troncato/malformato causava
   un 500 non gestito.
   → Aggiunto `except jwt.PyJWTError` con messaggio utente dedicato.

7. **Bug funzionale in `produttori.delete`** — `.format(id_produttore)` era
   applicato al valore di ritorno di `.execute()` (`None`) invece che alla
   stringa SQL: la cancellazione di un produttore falliva sempre.
   → Fix della posizione delle parentesi.

8. **Whitelist esplicita delle colonne modificabili** — `_update_user`
   (auth.py) e `produttori.create()`/`update()` costruivano l'`UPDATE`/
   `INSERT` usando come nomi di colonna le chiavi ricevute da `request.form`,
   protette solo per un effetto collaterale accidentale di `check_inputs_*`
   (KeyError su chiavi non previste). Poiché `check_inputs_utente` e
   `check_inputs_produttore` validano anche una chiave `id` "nuda" non
   presente nei form reali, un campo `id` aggiunto artificialmente a una
   richiesta poteva finire tra le colonne scritte.
   → Aggiunte whitelist esplicite (`COLONNE_UTENTE_MODIFICABILI`,
   `COLONNE_PRODUTTORE_MODIFICABILI`) applicate dopo la validazione.

9. **Atomicità delle doppie scritture in cassa.** `db.py` usa
   `conn.set_session(autocommit=True)`: ogni `execute()` era una transazione
   a sé, quindi `effettua_tesseramento`, `giroconto_utente` e il giroconto da
   `movimenti.handle()` potevano restare con una sola gamba del movimento
   scritta se la seconda falliva. In `effettua_tesseramento` inoltre, se
   l'utente FCA non esisteva, il codice inseriva comunque l'addebito
   all'utente e saltava in silenzio l'accredito.
   → Aggiunto `atomic()` in `db.py` (context manager che disattiva
   temporaneamente l'autocommit solo per il blocco, commit/rollback
   espliciti), usato nei tre punti sopra. In `effettua_tesseramento` la
   verifica dell'utente FCA ora avviene *prima* di scrivere qualunque riga,
   con errore visibile all'utente se manca. Corretto anche un bug analogo in
   `movimenti._handle`: il controllo "un giroconto necessita di due utenti
   diversi" avveniva *dopo* aver già inserito la prima riga.

10. **CSRF.** Nessun form aveva un token anti-CSRF.
    → Aggiunto `Flask-WTF` (`CSRFProtect`), un helper Jinja `csrf_field()`
    che inserisce il campo nascosto, e una pagina di errore 400 dedicata.
    Iniettato `{{ csrf_field() }}` in tutti i form POST del progetto (40, in
    27 template) con uno script mirato sul tag `<form ...method="post"...>`
    per gestire anche i tag multi-riga.

## Da valutare prima di andare in produzione

- **Stripe: passare da secret key a Restricted API Key (RAK).** Per ora in
  test usiamo una secret key (`sk_...`, accesso completo all'account) —
  prima del go-live va creata una RAK (`rk_...`) con solo i permessi su
  Checkout Sessions e Webhooks, sia per l'istanza DDGAS sia per l'account
  Stripe di produzione di Malatesta. Vale sia per `STRIPE_SECRET_KEY` che
  per eventuali chiavi analoghe di altri provider in futuro.

- **Soglia "credito basso" configurabile per tenant.** Portata in gasma
  (produzione Malatesta) come avviso persistente in `base.html` quando il
  saldo dell'utente loggato scende sotto una soglia, con link diretto a
  Ricarica (`delek/__init__.py`, `inject_saldo_basso()` + `SOGLIA_SALDO_BASSO`
  hardcoded a 20€). In DDGAS va resa un parametro in `regole:` di
  `associazione.yaml` (es. `regole.soglia_credito_basso`, accanto a
  `quota_associativa_annuale`), non un valore fisso nel codice: ogni GAS
  tenant ha ordini di grandezza di spesa diversi.

- **Far coprire al socio la commissione Stripe sulla ricarica**, invece di
  farla assorbire all'associazione (~1,5% + 0,25€ per carte europee, varia
  per account/paese). Stripe non ha un surcharge automatico per Checkout in
  un setup non-Connect: va calcolato l'importo da addebitare via carta
  (`importo_da_addebitare = (importo_richiesto + fissa) / (1 - percentuale)`)
  e accreditare in `movimenti` solo `importo_richiesto`, mostrando la
  commissione in `ricarica.html` prima della conferma. Se reso opzionale
  per tenant, anche questo andrebbe in `regole:` di `associazione.yaml`
  (percentuale/fissa possono differire per account Stripe).
