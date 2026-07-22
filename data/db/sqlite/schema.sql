PRAGMA foreign_keys=0;

DROP TABLE IF EXISTS nuovi_utenti;
DROP TABLE IF EXISTS referenze;
DROP TABLE IF EXISTS arruolati;
DROP TABLE IF EXISTS movimenti;
DROP TABLE IF EXISTS tipologie_movimenti;
DROP TABLE IF EXISTS dettagli_ordini;
DROP TABLE IF EXISTS produttori;
DROP TABLE IF EXISTS ordini;
DROP TABLE IF EXISTS ruoli;
DROP TABLE IF EXISTS utenti;

PRAGMA foreign_keys=1;

CREATE TABLE utenti (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  email TEXT NOT NULL,
  telefono TEXT,
  nome TEXT,
  cognome TEXT,
  attivo INTEGER DEFAULT 0
);

CREATE TABLE nuovi_utenti (
  id_utente INTEGER PRIMARY KEY,
  data_iscrizione TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id) ON DELETE CASCADE
);

CREATE TABLE produttori (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT UNIQUE NOT NULL,
  email TEXT,
  telefono TEXT,
  website TEXT,
  mask_mesi_consegna TEXT,
  prodotto_principale TEXT,
  descrizione TEXT,
  attivo INTEGER DEFAULT 1
);

CREATE TABLE ruoli (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ruolo TEXT NOT NULL,
  descrizione TEXT NOT NULL
);

CREATE TABLE arruolati (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_ruolo INTEGER NOT NULL,
  id_utente INTEGER NOT NULL,
  FOREIGN KEY (id_ruolo) REFERENCES ruoli (id),
  FOREIGN KEY (id_utente) REFERENCES utenti (id)
);

CREATE TABLE referenze (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
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
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_produttore INTEGER UNIQUE NOT NULL,
  scadenza TEXT NOT NULL,
  consegna TEXT NOT NULL,
  minimo_ordine REAL NOT NULL,
  nota TEXT,
  FOREIGN KEY (id_produttore) REFERENCES produttori (id)
);

-- gestore è l'id dell'utente che ha permesso il movimento
-- La gestione può avvenire da:
--  + tesoriere (versamenti, prelievi)
--  + referenti (rettifiche)
--  + applicativo (acquisti andati a buon fine) ID = 0 [default]
--  + utenti (donazioni ad altri utenti)
CREATE TABLE movimenti (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  per_id_utente INTEGER NOT NULL,
  -- puo' essere un utenti.id o produttori.id, si evince dalla tipologia
  verso_id INTEGER,
  gestore INTEGER DEFAULT 0,
  tipologia INTEGER DEFAULT 4,
  importo INTEGER NOT NULL,
  descrizione TEXT,
  effettuato_il TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (per_id_utente) REFERENCES utenti (id),
  FOREIGN KEY (tipologia) REFERENCES tipologie_movimenti (id)
);

CREATE TABLE tipologie_movimenti (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nome TEXT NOT NULL
);

-- SPECIFICI MALATESTA {{{

-- nei movimenti avremo es:
-- versamento: (da_id_utente: N, verso_id: N)
-- prelievo: (da_id_utente: N, verso_id: N)
-- rettifica: (da_id_utente: N, verso_id: N)
-- giroconto: (da_id_utente: N, verso_id: M)
-- acquisto: (da_id_utente: N, verso_id: J)
-- dove N, M sono utenti.id, J è un produttori.id
-- quindi per versamento, prelievo, rettifica da_id_utente = verso_id
insert into tipologie_movimenti (nome)
values ('versamento'), ('prelievo'), ('giroconto'), ('acquisto'), ('rettifica');

insert into ruoli (ruolo, descrizione)
values
  ('moderatore', 'Aggiunge produttori, assegna referenti, gestisce i membri'),
  ('referente', 'Gestisce un produttore'),
  ('segretario', 'Si occupa dei verbaili delle riunioni'),
  ('accoglienza', 'Introduce al gruppo i nuovi membri e li attiva agli acquisti'),
  ('tesoriere', 'Gestisce la cassa (versamenti e pagamenti annuali)');

--- }}}
