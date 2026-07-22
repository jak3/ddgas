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
  data_iscrizione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
  ruolo VARCHAR(40) NOT NULL, -- 'nome' sarebbe stato meglio che ne 'ruolo'
  descrizione TEXT NOT NULL
);

CREATE TABLE arruolati (
  id SERIAL PRIMARY KEY,
  id_ruolo INTEGER NOT NULL,
  id_utente INTEGER NOT NULL,
  FOREIGN KEY (id_ruolo) REFERENCES ruoli (id),
  FOREIGN KEY (id_utente) REFERENCES utenti (id)
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
  scadenza TIMESTAMP NOT NULL,
  consegna TIMESTAMP NOT NULL,
  minimo_ordine NUMERIC(7, 2) DEFAULT 0,
  nota TEXT,
  FOREIGN KEY (id_produttore) REFERENCES produttori (id)
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
  effettuato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (per_id_utente) REFERENCES utenti (id),
  FOREIGN KEY (tipologia) REFERENCES tipologie_movimenti (id)
);

CREATE TABLE presidi (
  id SERIAL PRIMARY KEY,
  giorno TIMESTAMP,
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
  consegna TIMESTAMP NOT NULL,
  dettaglio JSON,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_produttore) REFERENCES produttori (id)
);

CREATE TABLE pagamenti_ordini (
  id SERIAL PRIMARY KEY,
  id_produttore INTEGER NOT NULL,
  consegna TIMESTAMP NOT NULL,
  data_pagamento TIMESTAMP,
  FOREIGN KEY (id_produttore) REFERENCES produttori (id),
  UNIQUE (id_produttore, consegna)
);

CREATE TABLE campagne_tesseramenti (
  id SERIAL PRIMARY KEY,
  data_inizio TIMESTAMP NOT NULL,
  quota NUMERIC(7, 2) NOT NULL
);
