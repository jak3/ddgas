DROP TABLE IF EXISTS ricariche_esterne;
DROP TABLE IF EXISTS contenuti_editabili;
DROP TABLE IF EXISTS codici_ente_terzo;
DROP TABLE IF EXISTS nuovi_utenti;
DROP TABLE IF EXISTS referenze;
DROP TABLE IF EXISTS arruolati;
DROP TABLE IF EXISTS movimenti;
DROP TABLE IF EXISTS tipologie_movimenti;
DROP TABLE IF EXISTS dettagli_ordini;
DROP TABLE IF EXISTS produttori;
DROP TABLE IF EXISTS ruoli;
DROP TABLE IF EXISTS storico_ordini;
DROP TABLE IF EXISTS pagamenti_ordini;
DROP TABLE IF EXISTS campagne_tesseramenti;
DROP TABLE IF EXISTS utenti;

CREATE TABLE utenti (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  email TEXT NOT NULL,
  telefono TEXT,
  nome TEXT,
  cognome TEXT,
  attivo BOOLEAN DEFAULT FALSE,
  cf VARCHAR(16)
);

CREATE TABLE nuovi_utenti (
  id_utente INTEGER PRIMARY KEY,
  data_iscrizione TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id) ON DELETE CASCADE
);

CREATE TABLE produttori (
  id SERIAL PRIMARY KEY,
  nome TEXT UNIQUE NOT NULL,
  email TEXT,
  telefono TEXT,
  website TEXT,
  mask_mesi_consegna BIT(12),
  prodotto_principale TEXT,
  descrizione TEXT,
  attivo BOOLEAN DEFAULT TRUE
);

CREATE TABLE ruoli (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(40) NOT NULL,
  descrizione TEXT NOT NULL,
  attivo BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE arruolati (
  id SERIAL PRIMARY KEY,
  id_ruolo INTEGER NOT NULL,
  id_utente INTEGER NOT NULL,
  FOREIGN KEY (id_ruolo) REFERENCES ruoli (id),
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  UNIQUE (id_ruolo, id_utente)
);

CREATE TABLE referenze (
  id SERIAL PRIMARY KEY,
  id_produttore INTEGER NOT NULL,
  id_utente INTEGER NOT NULL,
  FOREIGN KEY (id_produttore) REFERENCES produttori (id),
  FOREIGN KEY (id_utente) REFERENCES utenti (id)
);

-- Si inseriranno da parte dei referenti, i dettagli per
-- apertura/chiusura/minimo_ordine di un produttore associato a una scadenza
-- (ultimo giorno per poter ordinare, associato anche a stato di apertura e
-- chiusura) e una consegna.
-- Fare sempre UPDATE (che se non presente INSERT) per id_produttore UNIQUE
CREATE TABLE dettagli_ordini (
  id SERIAL PRIMARY KEY,
  id_produttore INTEGER UNIQUE NOT NULL,
  scadenza TIMESTAMPTZ NOT NULL,
  consegna TIMESTAMPTZ NOT NULL,
  minimo_ordine NUMERIC(7, 2) NOT NULL DEFAULT 0,
  nota TEXT,
  promemoria_inviato BOOLEAN NOT NULL DEFAULT FALSE,
  FOREIGN KEY (id_produttore) REFERENCES produttori (id)
);

-- Iscrizione permanente: l'utente vuole essere avvisato per ogni futuro
-- ordine di questo produttore, non solo per quello attualmente aperto.
CREATE TABLE notifiche_produttore (
  id_utente INTEGER NOT NULL,
  id_produttore INTEGER NOT NULL,
  PRIMARY KEY (id_utente, id_produttore),
  FOREIGN KEY (id_utente) REFERENCES utenti (id) ON DELETE CASCADE,
  FOREIGN KEY (id_produttore) REFERENCES produttori (id) ON DELETE CASCADE
);

-- Iscrizione una tantum, solo per l'ordine attualmente aperto: la riga
-- referenziata sparisce (CASCADE) quando l'ordine chiude, non si trascina
-- sul ciclo d'ordine successivo dello stesso produttore.
CREATE TABLE notifiche_ordine (
  id_utente INTEGER NOT NULL,
  id_dettaglio_ordine INTEGER NOT NULL,
  PRIMARY KEY (id_utente, id_dettaglio_ordine),
  FOREIGN KEY (id_utente) REFERENCES utenti (id) ON DELETE CASCADE,
  FOREIGN KEY (id_dettaglio_ordine) REFERENCES dettagli_ordini (id) ON DELETE CASCADE
);

CREATE TABLE tipologie_movimenti (
  id SMALLINT PRIMARY KEY,
  nome VARCHAR(40) NOT NULL
);

-- gestore è l'id dell'utente che ha permesso il movimento
-- La gestione può avvenire da:
--  + tesoriere (versamenti, prelievi)
--  + referenti (rettifiche)
--  + applicativo (acquisti andati a buon fine) ID = 0 [default]
--  + utenti (donazioni ad altri utenti)
CREATE TABLE movimenti (
  id SERIAL PRIMARY KEY,
  per_id_utente INTEGER,
  gestore INTEGER DEFAULT 0,
  tipologia SMALLINT DEFAULT 4,
  importo NUMERIC(7, 2) NOT NULL,
  descrizione TEXT,
  effettuato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (per_id_utente) REFERENCES utenti (id),
  FOREIGN KEY (tipologia) REFERENCES tipologie_movimenti (id)
);

-- Traccia le ricariche avviate tramite un gateway di pagamento esterno
-- (Stripe, Satispay, PayPal, ...). provider_ref è l'id che il gateway
-- assegna all'operazione (es. Stripe Checkout Session id): la UNIQUE su
-- (provider, provider_ref) è quello che garantisce che una notifica/webhook
-- duplicata non accrediti due volte lo stesso pagamento.
CREATE TABLE ricariche_esterne (
  id SERIAL PRIMARY KEY,
  provider VARCHAR(40) NOT NULL,
  provider_ref TEXT NOT NULL,
  id_utente INTEGER NOT NULL,
  importo NUMERIC(7, 2) NOT NULL,
  stato VARCHAR(20) NOT NULL DEFAULT 'creato',
  id_movimento INTEGER,
  creato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_movimento) REFERENCES movimenti (id),
  UNIQUE (provider, provider_ref)
);

CREATE TABLE presidi (
  id SERIAL PRIMARY KEY,
  giorno TIMESTAMPTZ,
  id_utente INTEGER,
  FOREIGN KEY (id_utente) REFERENCES utenti (id)
);

CREATE TABLE storico_ordini (
  id SERIAL PRIMARY KEY,
  id_utente INTEGER NOT NULL,
  id_produttore INTEGER NOT NULL,
  -- Permetto il valore NULL in modo da mantenere lo storico a fronte di un
  -- azzeramento di tutti i movimenti (esempio cambio di Conto Corrente)
  id_movimento INTEGER,
  importo NUMERIC(7, 2) NOT NULL,
  consegna TIMESTAMPTZ NOT NULL,
  dettaglio JSON,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_produttore) REFERENCES produttori (id)
);

CREATE TABLE pagamenti_ordini (
  id SERIAL PRIMARY KEY,
  id_produttore INTEGER NOT NULL,
  consegna TIMESTAMPTZ NOT NULL,
  data_pagamento TIMESTAMPTZ,
  FOREIGN KEY (id_produttore) REFERENCES produttori (id),
  UNIQUE (id_produttore, consegna)
);

CREATE TABLE campagne_tesseramenti (
  id SERIAL PRIMARY KEY,
  data_inizio TIMESTAMPTZ NOT NULL,
  quota NUMERIC(7, 2) NOT NULL
);

-- Codice di una tessera di un ente terzo (es. ARCI), tracciato solo come
-- informazione facoltativa: creata sempre, indipendentemente da
-- associazione.regole.tessera_ente_terzo.richiesta, che controlla solo se
-- la UI la mostra (stesso pattern di ricariche_esterne per Stripe/Satispay).
CREATE TABLE codici_ente_terzo (
  id_utente INTEGER PRIMARY KEY,
  codice TEXT,
  FOREIGN KEY (id_utente) REFERENCES utenti (id) ON DELETE CASCADE
);

-- Blocchi di testo di alcune pagine (es. l'introduzione discorsiva di
-- istruzioni/acquisto.html) modificabili da un moderatore senza toccare il
-- codice. Se non è presente una riga per uno slug, il controller usa un
-- default hardcoded: questa tabella parte quindi vuota, non richiede seed.
CREATE TABLE contenuti_editabili (
  slug TEXT PRIMARY KEY,
  contenuto TEXT NOT NULL,
  aggiornato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  aggiornato_da INTEGER,
  FOREIGN KEY (aggiornato_da) REFERENCES utenti (id)
);
