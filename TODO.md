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

## Da valutare (interventi più ampi, non ancora fatti)

- **Atomicità delle doppie scritture in cassa.** `db.py` usa
  `conn.set_session(autocommit=True)`: ogni `execute()` è una transazione a
  sé. `effettua_tesseramento`, `giroconto_utente` e simili inseriscono due
  righe collegate (es. -8€ utente / +8€ FCA) con due `INSERT` separati e
  autocommittati — se il secondo fallisce (utente FCA non trovato,
  eccezione, timeout) resta silenziosamente solo una gamba del movimento,
  senza errore visibile. Richiede di avvolgere questi flussi in transazioni
  esplicite (o quantomeno loggare/segnalare un fallimento parziale);
  probabilmente non va toccato il default globale di autocommit senza
  verificare tutte le altre query che vi fanno affidamento.

- **CSRF.** Nessun form dell'app ha un token anti-CSRF. Ora che gli endpoint
  distruttivi sono POST-only questo non è più bypassabile con un semplice
  link, ma un moderatore/tesoriere autenticato potrebbe comunque essere
  indotto (pagina malevola di terzi) a inviare una POST a sua insaputa.
  Valutare `flask-wtf` o equivalente, con priorità sulle route con
  `@is_ruolo(['moderatore', ...])`.

## In corso — indagine dato mancante utente 51 (campagna 2025/2026)

Vedi thread di lavoro: il conteggio -8€/+8€ risulta bilanciato (65/65), il
che è coerente con la cancellazione di **entrambe** le gambe del movimento di
un solo utente (es. tramite il bug del punto 1, prima del fix) — non prova
che il movimento non sia mai esistito. Da verificare con log del webserver
o backup del DB per confermare.
