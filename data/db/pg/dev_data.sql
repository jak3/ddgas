DROP TABLE IF EXISTS ordine_in_corso_6 CASCADE;
DROP TABLE IF EXISTS ordine_in_corso_5 CASCADE;
DROP TABLE IF EXISTS ordine_in_corso_4 CASCADE;
DROP TABLE IF EXISTS ordine_in_corso_3 CASCADE;
DROP TABLE IF EXISTS ordine_in_corso_2 CASCADE;
DROP TABLE IF EXISTS ordine_in_corso_1 CASCADE;
DROP TABLE IF EXISTS listino_6 CASCADE;
DROP TABLE IF EXISTS listino_5 CASCADE;
DROP TABLE IF EXISTS listino_4 CASCADE;
DROP TABLE IF EXISTS listino_3 CASCADE;
DROP TABLE IF EXISTS listino_2 CASCADE;
DROP TABLE IF EXISTS listino_1 CASCADE;

insert into utenti (username, password, email, attivo)
values
  ('mode',  'pbkdf2:sha256:150000$JM9fIjKz$a222769c12b6762408541733cf9dd0b19aab810761c81dce8a76dfcd706c5f86', 'user1@gmail.com', TRUE),
  ('refe',  'pbkdf2:sha256:150000$6uRZPfEi$60c150835bfb4967057f0234a353fc8b106c0b42bce7ff57fd58274e62c85971', 'user2@gmail.com', TRUE),
  ('teso',  'pbkdf2:sha256:150000$Jf10mGNL$7f3324f1a71325e98f5702ebd70bd4d1285601286d7d37533942af21d2c1f33d', 'user3@gmail.com', TRUE),
  ('user4', 'pbkdf2:sha256:150000$IISKThpf$f038a4defdd6acdb7ebd8187f397a53cf3ad250c4a50fd1d78de663df7ed4ff6', 'user4@gmail.com', TRUE),
  ('allin', 'pbkdf2:sha256:150000$1PB0mxpF$51024e5c527f6e73a49d62fe603f868f9e472ad5010358b47e376bab3a5f2e52', 'user5@gmail.com', TRUE),
  ('new10', 'pbkdf2:sha256:150000$f1ADBiyF$0c831b0f5bed7ea1b7caf25f35651fb193cf5f9ebc81285a7c9f268af87bc3db', 'user6@gmail.com', FALSE),
  ('new11', 'pbkdf2:sha256:150000$I0e9xFD5$94b756048a90394454238523911915208cc06e38f92a64dc815759bbb97f043c', 'user7@gmail.com', FALSE),
  ('new12', 'pbkdf2:sha256:150000$3ysVXsuj$43ac0bb5c404ef01c16b86aa5aff31833c89c7a2d4d60b892458f47331ee8e6f', 'user8@gmail.com', FALSE),
  ('new20', 'pbkdf2:sha256:150000$4UNwzE0k$a0351a9be6230aa93175b17526161fb0a94e6040d2c5b3a4090e486452d20ad7', 'user9@gmail.com', FALSE) ON CONFLICT DO NOTHING;

insert into nuovi_utenti (id_utente) values (6),(7),(8),(9) ON CONFLICT DO NOTHING;

insert into produttori (nome, email, telefono, website, mask_mesi_consegna, prodotto_principale, descrizione, attivo)
values
  ('Rivalta', 'prd1@gmail.com', '012345', 'https://prod1-verd.com', '101111111111', 'Verdura', 'Biodinamica',TRUE),
  ('Galline Felici', 'prd2@gmail.com', '022355', 'https://prod2-frut.com', '110011011111', 'Frutta', 'Locale, antica, dolce',TRUE),
  ('Chicco Buono', 'prd3@gmail.com', '032365', 'https://prod3-vefr.com', '110111101111', 'Caffe', 'Tostatura del tutto naturale',TRUE),
  ('Blu di Persia', 'prd4@gmail.com', '042375', 'https://prod4-sali.com', '110010001111', 'Sale', 'Sali della Terra',TRUE),
  ('Senza', 'ssenza@gmail.com', '102345', 'https://essenza-verde.com', '101110011111', 'Oli Essenziali', 'Oli Essenziali da Piante officinali',FALSE),
  ('Torri', 'prd5@gmail.com', '052385', 'https://prod5-miel.com', '110010001001', 'Miele', 'Api libere', TRUE) ON CONFLICT DO NOTHING;

insert into arruolati (id_ruolo, id_utente)
values
  (1, 1),
  (1, 2),
  (1, 5),
  (2, 2),
  (2, 4),
  (2, 5),
  (3, 5),
  (3, 3),
  (4, 5),
  (5, 5) ON CONFLICT DO NOTHING;

insert into referenze(id_produttore, id_utente)
values
  (2, 2),
  (5, 4),
  (3, 5) ON CONFLICT DO NOTHING;

CREATE TABLE listino_1 (
  id SERIAL PRIMARY KEY,
  categoria TEXT DEFAULT '',
  disponibile BOOLEAN DEFAULT TRUE,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo NUMERIC(7, 2) NOT NULL,
  n_min_colli INTEGER DEFAULT 1,
  n_max_colli INTEGER DEFAULT 0,
  colli_disponibili INTEGER DEFAULT 0,
  nota TEXT
);

insert into listino_1 (disponibile, categoria, descrizione_prodotto, dettaglio_qta, prezzo, n_min_colli, nota)
values
  (TRUE, '', 'Prodotto 1 ', '1kg', 1 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 2 ', NULL, 2.0 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 3 ', '3kg', 3.1 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 4 ', '4kg', 4.2 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 5 ', '5kg', 5.3 , 5, NULL),
  (FALSE, 'unita', 'Prodotto 6 ', '6kg', 6.4 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 7 ', '7kg', 7.5 , 1, 'solo per <saturno>'),
  (TRUE, 'unita', 'Prodotto 8 ', '8kg', 8.6 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 9 ', '9kg', 9.7 , 1, NULL),
  (TRUE, '', 'Prodotto 10', NULL, 10, 1, NULL),
  (TRUE, 'decin', 'Prodotto 11', '1l', 11, 1, NULL),
  (TRUE, 'decin', 'Prodotto 12', '2l', 12, 1, 'NON CI PROVARE'),
  (TRUE, 'decin', 'Prodotto 13', '3l', 13.99, 1, NULL);

CREATE TABLE listino_2 (
  id SERIAL PRIMARY KEY,
  categoria TEXT DEFAULT '',
  disponibile BOOLEAN DEFAULT TRUE,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo NUMERIC(7, 2) NOT NULL,
  n_min_colli INTEGER DEFAULT 1,
  n_max_colli INTEGER DEFAULT 0,
  colli_disponibili INTEGER DEFAULT 0,
  nota TEXT
);

CREATE TABLE listino_3 (
  id SERIAL PRIMARY KEY,
  categoria TEXT DEFAULT '',
  disponibile BOOLEAN DEFAULT TRUE,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo NUMERIC(7, 2) NOT NULL,
  n_min_colli INTEGER DEFAULT 1,
  n_max_colli INTEGER DEFAULT 0,
  colli_disponibili INTEGER DEFAULT 0,
  nota TEXT
);

insert into listino_3 (disponibile, categoria, descrizione_prodotto, dettaglio_qta, prezzo, n_min_colli, nota)
values
  (TRUE, '', 'Prodotto 1 ', '1kg', 1 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 2 ', NULL, 2.0 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 3 ', '3kg', 3.1 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 4 ', '4kg', 4.2 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 5 ', '5kg', 5.3 , 5, NULL),
  (FALSE, 'unita', 'Prodotto 6 ', '6kg', 6.4 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 7 ', '7kg', 7.5 , 1, 'solo per <saturno>'),
  (TRUE, 'unita', 'Prodotto 8 ', '8kg', 8.6 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 9 ', '9kg', 9.7 , 1, NULL),
  (TRUE, '', 'Prodotto 10', NULL, 10, 1, NULL),
  (TRUE, 'decin', 'Prodotto 11', '1l', 11, 1, NULL),
  (TRUE, 'decin', 'Prodotto 12', '2l', 12, 1, 'NON CI PROVARE'),
  (TRUE, 'decin', 'Prodotto 13', '3l', 13.99, 1, NULL);

CREATE TABLE listino_4 (
  id SERIAL PRIMARY KEY,
  categoria TEXT DEFAULT '',
  disponibile BOOLEAN DEFAULT TRUE,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo NUMERIC(7, 2) NOT NULL,
  n_min_colli INTEGER DEFAULT 1,
  n_max_colli INTEGER DEFAULT 0,
  colli_disponibili INTEGER DEFAULT 0,
  nota TEXT
);

insert into listino_4 (disponibile, categoria, descrizione_prodotto, dettaglio_qta, prezzo, n_min_colli, nota)
values
  (TRUE, '', 'Prodotto 1 ', '1kg', 1 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 2 ', NULL, 2.0 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 3 ', '3kg', 3.1 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 4 ', '4kg', 4.2 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 5 ', '5kg', 5.3 , 5, NULL),
  (FALSE, 'unita', 'Prodotto 6 ', '6kg', 6.4 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 7 ', '7kg', 7.5 , 1, 'solo per <saturno>'),
  (TRUE, 'unita', 'Prodotto 8 ', '8kg', 8.6 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 9 ', '9kg', 9.7 , 1, NULL),
  (TRUE, '', 'Prodotto 10', NULL, 10, 1, NULL),
  (TRUE, 'decin', 'Prodotto 11', '1l', 11, 1, NULL),
  (TRUE, 'decin', 'Prodotto 12', '2l', 12, 1, 'NON CI PROVARE'),
  (TRUE, 'decin', 'Prodotto 13', '3l', 13.99, 1, NULL);

CREATE TABLE listino_5 (
  id SERIAL PRIMARY KEY,
  categoria TEXT DEFAULT '',
  disponibile BOOLEAN DEFAULT TRUE,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo NUMERIC(7, 2) NOT NULL,
  n_min_colli INTEGER DEFAULT 1,
  n_max_colli INTEGER DEFAULT 0,
  colli_disponibili INTEGER DEFAULT 0,
  nota TEXT
);

insert into listino_5 (disponibile, categoria, descrizione_prodotto, dettaglio_qta, prezzo, n_min_colli, nota)
values
  (TRUE, '', 'Prodotto 1 ', '1kg', 1 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 2 ', NULL, 2.0 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 3 ', '3kg', 3.1 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 4 ', '4kg', 4.2 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 5 ', '5kg', 5.3 , 5, NULL),
  (FALSE, 'unita', 'Prodotto 6 ', '6kg', 6.4 , 1, NULL),
  (FALSE, 'unita', 'Prodotto 7 ', '7kg', 7.5 , 1, 'solo per <saturno>'),
  (TRUE, 'unita', 'Prodotto 8 ', '8kg', 8.6 , 1, NULL),
  (TRUE, 'unita', 'Prodotto 9 ', '9kg', 9.7 , 1, NULL),
  (TRUE, '', 'Prodotto 10', NULL, 10, 1, NULL),
  (TRUE, 'decin', 'Prodotto 11', '1l', 11, 1, NULL),
  (TRUE, 'decin', 'Prodotto 12', '2l', 12, 1, 'NON CI PROVARE'),
  (TRUE, 'decin', 'Prodotto 13', '3l', 13.99, 1, NULL);

CREATE TABLE listino_6 (
  id SERIAL PRIMARY KEY,
  categoria TEXT DEFAULT '',
  disponibile BOOLEAN DEFAULT TRUE,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo NUMERIC(7, 2) NOT NULL,
  n_min_colli INTEGER DEFAULT 1,
  n_max_colli INTEGER DEFAULT 0,
  colli_disponibili INTEGER DEFAULT 0,
  nota TEXT
);

CREATE TABLE ordine_in_corso_1 (
  id SERIAL PRIMARY KEY,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti SMALLINT NOT NULL,
  specifica TEXT,
  effettuato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_1 (id)
);

CREATE TABLE ordine_in_corso_2 (
  id SERIAL PRIMARY KEY,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti SMALLINT NOT NULL,
  specifica TEXT,
  effettuato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_2 (id)
);

CREATE TABLE ordine_in_corso_3 (
  id SERIAL PRIMARY KEY,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti SMALLINT NOT NULL,
  specifica TEXT,
  effettuato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_3 (id)
);

CREATE TABLE ordine_in_corso_4 (
  id SERIAL PRIMARY KEY,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti SMALLINT NOT NULL,
  specifica TEXT,
  effettuato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_4 (id)
);

CREATE TABLE ordine_in_corso_5 (
  id SERIAL PRIMARY KEY,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti SMALLINT NOT NULL,
  specifica TEXT,
  -- Utilizzato per priorità ?
  effettuato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_5 (id)
);

CREATE TABLE ordine_in_corso_6 (
  id SERIAL PRIMARY KEY,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti SMALLINT NOT NULL,
  specifica TEXT,
  effettuato_il TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_1 (id)
);

insert into ordine_in_corso_1 (id_utente, id_prodotto, colli_richiesti, effettuato_il)
values
  (5,1,1,'2021-02-21'),
  (5,5,5,'2021-02-21'),
  (5,10,8,'2021-02-21'),
  (5,2,2,'2021-02-21'),
  (5,8,4,'2021-02-21'),
  (3,4,1,'2021-02-22'),
  (3,9,5,'2021-02-22'),
  (3,12,8,'2021-02-22'),
  (3,10,2,'2021-02-22'),
  (3,13,4,'2021-02-22');

insert into ordine_in_corso_3 (id_utente, id_prodotto, colli_richiesti, effettuato_il)
values
  (5,1,1,'2021-02-21'),
  (5,5,5,'2021-02-21'),
  (5,10,8,'2021-02-21'),
  (5,2,2,'2021-02-21'),
  (5,8,4,'2021-02-21');

insert into dettagli_ordini (id_produttore, scadenza, consegna, nota, minimo_ordine)
values
  (1, '2021-05-25', '2021-05-30', 'Ultima settimana per i lischi', 0),
  (2, '2021-02-25', '2021-03-21', NULL, 0),
  (3, '2021-02-03', '2021-02-21', 'Packaging nuovo', 400),
  (5, '2020-08-09', '2020-10-21', NULL, 0) ON CONFLICT DO NOTHING;

-- Le rettifiche presenti nei movimenti, sono da considerare solo nel caso un
-- referente si sbagli durante la fase di chiusura di un ordine, in cui viene
-- sistemato l'importo di acquisto corretto (dal referente una volta consegnato)
-- + gestore: CHI ha effettuato il movimento, nel caso degli acquisti, sarà
-- l'applicativo, quindi per convenzione, id 0 (vedi DEFAULT in CREATE TABLE)
-- + tipologia: vedi tabella tipologie_movimenti, inserito l'ID
insert into movimenti
(per_id_utente, gestore, tipologia, effettuato_il, importo)
values
  (1,5,1,'2019-02-12','100'),
  (2,5,1,'2019-03-12','80'),
  (3,5,1,'2019-04-12','40'),
  (5,5,1,'2019-05-12','20'),
  (2,5,2,'2020-02-12','-10'),
  (2,5,2,'2020-03-12','-15'),
  (1,5,3,'2020-04-12','-20'),
  (2,5,3,'2020-04-12','20'),
  (1,0,4,'2021-12-12','10'),
  (2,0,4,'2021-11-12','10.99'),
  (3,0,4,'2021-11-12','10'),
  (5,0,4,'2021-11-12','10.99') ON CONFLICT DO NOTHING;
