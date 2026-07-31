# Attivare una nuova istanza per un GAS

Checklist per configurare DDGAS per una nuova associazione. Ogni istanza è
un deploy a sé (un `associazione.yaml`, un DB, un hosting): non c'è
multi-tenancy a runtime, l'hosting/provider resta una scelta del singolo
cliente.

## 1. Dati da richiedere al cliente

**Identità e dati pubblici** (vanno in `config/associazione.yaml`):

- Nome completo e nome breve dell'associazione
- Tagline/sottotitolo
- Indirizzo e codice fiscale (partita IVA se presente)
- Colore primario del brand (hex)
- Logo e favicon (immagini, vanno in `delek/static/`; finché non forniti
  restano i placeholder generici di default)
- Email di contatto generale e tecnica
- Dati bancari: IBAN, intestazione conto, nome banca
- Quota associativa annuale
- Se è richiesta una tessera di un ente terzo (es. ARCI) per l'iscrizione,
  e il nome dell'ente

**Contenuti testuali** (documenti, non dati strutturati — chiedere i file
o il testo già scritto dal cliente, non improvvisarli):

- Statuto/Regolamento associativo completo → `delek/templates/regolamento.html`
  (attualmente un segnaposto con indice esemplificativo, da sostituire
  per intero)
- Testo di presentazione "Chi Siamo" (storia fondativa, dove/quando è
  nata l'associazione) → paragrafo finale di `delek/templates/chi-siamo.html`
- Dettagli operativi dei turni di presidio/consegna (orari, indirizzo
  email per segnalazioni, indicazioni sulla sede) → `delek/templates/presidi/vademecum.html`,
  se l'associazione usa la funzionalità Presidi

**Pagamenti** (opzionali, il modulo Ricariche resta disattivato finché
non sono configurati — vedi `PAGAMENTI_ABILITATI`/`SATISPAY_ABILITATO`
in `DEV.md`):

- Vuole abilitare le ricariche con carta (Stripe)? Serve un account Stripe
  del cliente (o gestito per suo conto)
- Vuole abilitare anche Satispay?
- Chi si fa carico dell'eventuale commissione del gateway (vedi TODO.md,
  ancora da implementare)

## 2. File da modificare per una nuova istanza

- `config/associazione.yaml` — tutti i dati pubblici sopra
- `delek/static/<logo>` — aggiungere l'immagine reale, aggiornare
  `branding.logo` in `associazione.yaml` con il nome file (di default punta
  a `logo-placeholder.svg`, un segnaposto generico)
- `delek/static/<favicon>` — stesso discorso per `branding.favicon`
  (default `favicon-placeholder.svg`)
- `delek/templates/regolamento.html` — sostituire il segnaposto
- `delek/templates/chi-siamo.html` — sostituire il paragrafo finale
  (segnato con un commento `<!-- SEGNAPOSTO -->`)
- `delek/templates/presidi/vademecum.html` — adattare se si usano i
  Presidi

## 3. Setup DB

```
createdb <nome_db>
psql <nome_db> -f data/db/pg/schema.sql
psql <nome_db> -f data/db/pg/bootstrap.sql
```

`bootstrap.sql` crea solo i dati minimi richiesti dal codice (tipologie di
movimento, ruoli), nessun dato reale.

Dopo il primo avvio, crea il primo utente moderatore con:

```
flask create-admin
```

(chiede username/email/password interattivamente; l'utente creato è già
attivo e con ruolo moderatore, senza passare dal flusso di attivazione via
email). Se si useranno i tesseramenti, va creato anche un utente `FCA`
(fondo cassa associazione) che riceve gli accrediti delle quote — vedi
`effettua_tesseramento()` in `auth.py`; nessun comando dedicato per ora,
va fatto da interfaccia (Membri → assegna ruolo) o a mano in DB.

## 4. Variabili d'ambiente

Vedi `DEV.md` per l'elenco completo (`SECRET_KEY`, `DATABASE_URL`,
`SENDGRID_API_KEY`/`SENDGRID_FROM_EMAIL`, `STRIPE_SECRET_KEY`/
`STRIPE_WEBHOOK_SECRET`, `SATISPAY_KEY_ID`/`SATISPAY_PRIVATE_KEY`).

## 5. Deploy

Il deploy (Heroku, Docker o altro) resta una scelta del cliente/provider:
vedi `DEV.md` per le istruzioni Heroku attualmente documentate.
