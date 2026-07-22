DROP TABLE IF EXISTS ordine_in_corso_5;
DROP TABLE IF EXISTS ordine_in_corso_4;
DROP TABLE IF EXISTS ordine_in_corso_3;
DROP TABLE IF EXISTS ordine_in_corso_2;
DROP TABLE IF EXISTS ordine_in_corso_1;
DROP TABLE IF EXISTS listino_6;
DROP TABLE IF EXISTS listino_5;
DROP TABLE IF EXISTS listino_4;
DROP TABLE IF EXISTS listino_3;
DROP TABLE IF EXISTS listino_2;
DROP TABLE IF EXISTS listino_1;

insert into utenti (username, password, email, attivo)
values
  ('mode', 'pbkdf2:sha256:150000$M3fEKsQ8$2bdef2a755bfe8be21e6c97512fffcc0dc58b9878470f0ba38ff6618c3bf0752', 'user1@gmail.com', 1),
  ('refe', 'pbkdf2:sha256:150000$iEL42DFm$02d779bca75655ab84231d8ed890ddfd5e19d2c8c62cdac5fe9bd577de548b84', 'user2@gmail.com', 1),
  ('teso', 'pbkdf2:sha256:150000$mBLIsbKG$7bb9940840d0044b5f52897b6532afaee371b0ec2727189820ea07602a659327', 'user3@gmail.com', 1),
  ('user4', 'pbkdf2:sha256:150000$fL2T7W6M$a9729f3dd93e40b987938e4ace131c2abde2112e61b0e6bee19fe66cad7fd4d0', 'user4@gmail.com', 1),
  ('allin', 'pbkdf2:sha256:150000$Mn3PFLq9$fc741b8049677adc60df72b1d1c6257c14110eb78187900e1985b4fc1e91e411', 'user5@gmail.com', 1),
  ('new10', 'pbkdf2:sha256:150000$Mn3PFLq9$fc741b8049677adc60df72b1d1c6257c14110eb78187900e1985b4fc1e91e411', 'user6@gmail.com', 0),
  ('new11', 'pbkdf2:sha256:150000$Mn3PFLq9$fc741b8049677adc60df72b1d1c6257c14110eb78187900e1985b4fc1e91e411', 'user7@gmail.com', 0),
  ('new12', 'pbkdf2:sha256:150000$Mn3PFLq9$fc741b8049677adc60df72b1d1c6257c14110eb78187900e1985b4fc1e91e411', 'user8@gmail.com', 0),
  ('new20', 'pbkdf2:sha256:150000$Mn3PFLq9$fc741b8049677adc60df72b1d1c6257c14110eb78187900e1985b4fc1e91e411', 'user9@gmail.com', 0);

insert into nuovi_utenti (id_utente) values (6),(7),(8),(9);

insert into produttori (nome, email, telefono, website, mask_mesi_consegna, prodotto_principale, descrizione, attivo)
values
  ('Rivalta', 'prd1@gmail.com', '012345', 'https://prod1-verd.com', '101111111111', 'Verdura', 'Biodinamica',1),
  ('Galline Felici', 'prd2@gmail.com', '022355', 'https://prod2-frut.com', '110011011111', 'Frutta', 'Locale, antica, dolce',1),
  ('Malatesta', 'prd3@gmail.com', '032365', 'https://prod3-vefr.com', '110111101111', 'Caffe', 'Tostatura del tutto naturale',1),
  ('Blu di Persia', 'prd4@gmail.com', '042375', 'https://prod4-sali.com', '110010001111', 'Sale', 'Sali della Terra',1),
  ('Senza', 'ssenza@gmail.com', '102345', 'https://essenza-verde.com', '101110011111', 'Oli Essenziali', 'Oli Essenziali da Piante officinali',0),
  ('Torri', 'prd5@gmail.com', '052385', 'https://prod5-miel.com', '110010001001', 'Miele', 'Api libere', 1);

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
  (5, 5);

insert into referenze(id_produttore, id_utente)
values
  (2, 2),
  (5, 4),
  (3, 5);

CREATE TABLE listino_1 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  categoria TEXT,
  disponibile INTEGER DEFAULT 1,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo REAL NOT NULL,
  n_min_colli INTEGER NOT NULL DEFAULT 1,
  nota TEXT
);

insert into listino_1 (disponibile, categoria, descrizione_prodotto, dettaglio_qta, prezzo, n_min_colli, nota)
values
  (1, NULL, 'Prodotto 1 ', '1kg', 1 , 1, NULL),
  (0, 'unita', 'Prodotto 2 ', NULL, 2.0 , 1, NULL),
  (0, 'unita', 'Prodotto 3 ', '3kg', 3.1 , 1, NULL),
  (1, 'unita', 'Prodotto 4 ', '4kg', 4.2 , 1, NULL),
  (1, 'unita', 'Prodotto 5 ', '5kg', 5.3 , 5, NULL),
  (0, 'unita', 'Prodotto 6 ', '6kg', 6.4 , 1, NULL),
  (0, 'unita', 'Prodotto 7 ', '7kg', 7.5 , 1, 'solo per <saturno>'),
  (1, 'unita', 'Prodotto 8 ', '8kg', 8.6 , 1, NULL),
  (1, 'unita', 'Prodotto 9 ', '9kg', 9.7 , 1, NULL),
  (1, NULL, 'Prodotto 10', NULL, 10, 1, NULL),
  (1, 'decin', 'Prodotto 11', '1l', 11, 1, NULL),
  (1, 'decin', 'Prodotto 12', '2l', 12, 1, 'NON CI PROVARE'),
  (1, 'decin', 'Prodotto 13', '3l', 13.99, 1, NULL);

CREATE TABLE listino_2 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  categoria TEXT,
  disponibile INTEGER DEFAULT 1,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo REAL NOT NULL,
  n_min_colli INTEGER NOT NULL DEFAULT 1,
  nota TEXT
);

CREATE TABLE listino_3 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  categoria TEXT,
  disponibile INTEGER DEFAULT 1,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo REAL NOT NULL,
  n_min_colli INTEGER NOT NULL DEFAULT 1,
  nota TEXT
);

insert into listino_3 (disponibile, categoria, descrizione_prodotto, dettaglio_qta, prezzo, n_min_colli, nota)
values
  (1, NULL, 'Prodotto 1 ', '1kg', 1 , 1, NULL),
  (0, 'unita', 'Prodotto 2 ', NULL, 2.0 , 1, NULL),
  (0, 'unita', 'Prodotto 3 ', '3kg', 3.1 , 1, NULL),
  (1, 'unita', 'Prodotto 4 ', '4kg', 4.2 , 1, NULL),
  (1, 'unita', 'Prodotto 5 ', '5kg', 5.3 , 5, NULL),
  (0, 'unita', 'Prodotto 6 ', '6kg', 6.4 , 1, NULL),
  (0, 'unita', 'Prodotto 7 ', '7kg', 7.5 , 1, 'solo per <saturno>'),
  (1, 'unita', 'Prodotto 8 ', '8kg', 8.6 , 1, NULL),
  (1, 'unita', 'Prodotto 9 ', '9kg', 9.7 , 1, NULL),
  (1, NULL, 'Prodotto 10', NULL, 10, 1, NULL),
  (1, 'decin', 'Prodotto 11', '1l', 11, 1, NULL),
  (1, 'decin', 'Prodotto 12', '2l', 12, 1, 'NON CI PROVARE'),
  (1, 'decin', 'Prodotto 13', '3l', 13.99, 1, NULL);

CREATE TABLE listino_4 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  categoria TEXT,
  disponibile INTEGER DEFAULT 1,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo REAL NOT NULL,
  n_min_colli INTEGER NOT NULL DEFAULT 1,
  nota TEXT
);

insert into listino_4 (disponibile, categoria, descrizione_prodotto, dettaglio_qta, prezzo, n_min_colli, nota)
values
  (1, NULL, 'Prodotto 1 ', '1kg', 1 , 1, NULL),
  (0, 'unita', 'Prodotto 2 ', NULL, 2.0 , 1, NULL),
  (0, 'unita', 'Prodotto 3 ', '3kg', 3.1 , 1, NULL),
  (1, 'unita', 'Prodotto 4 ', '4kg', 4.2 , 1, NULL),
  (1, 'unita', 'Prodotto 5 ', '5kg', 5.3 , 5, NULL),
  (0, 'unita', 'Prodotto 6 ', '6kg', 6.4 , 1, NULL),
  (0, 'unita', 'Prodotto 7 ', '7kg', 7.5 , 1, 'solo per <saturno>'),
  (1, 'unita', 'Prodotto 8 ', '8kg', 8.6 , 1, NULL),
  (1, 'unita', 'Prodotto 9 ', '9kg', 9.7 , 1, NULL),
  (1, NULL, 'Prodotto 10', NULL, 10, 1, NULL),
  (1, 'decin', 'Prodotto 11', '1l', 11, 1, NULL),
  (1, 'decin', 'Prodotto 12', '2l', 12, 1, 'NON CI PROVARE'),
  (1, 'decin', 'Prodotto 13', '3l', 13.99, 1, NULL);

CREATE TABLE listino_5 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  categoria TEXT,
  disponibile INTEGER DEFAULT 1,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo REAL NOT NULL,
  n_min_colli INTEGER NOT NULL DEFAULT 1,
  nota TEXT
);

insert into listino_5 (disponibile, categoria, descrizione_prodotto, dettaglio_qta, prezzo, n_min_colli, nota)
values
  (1, NULL, 'Prodotto 1 ', '1kg', 1 , 1, NULL),
  (0, 'unita', 'Prodotto 2 ', NULL, 2.0 , 1, NULL),
  (0, 'unita', 'Prodotto 3 ', '3kg', 3.1 , 1, NULL),
  (1, 'unita', 'Prodotto 4 ', '4kg', 4.2 , 1, NULL),
  (1, 'unita', 'Prodotto 5 ', '5kg', 5.3 , 5, NULL),
  (0, 'unita', 'Prodotto 6 ', '6kg', 6.4 , 1, NULL),
  (0, 'unita', 'Prodotto 7 ', '7kg', 7.5 , 1, 'solo per <saturno>'),
  (1, 'unita', 'Prodotto 8 ', '8kg', 8.6 , 1, NULL),
  (1, 'unita', 'Prodotto 9 ', '9kg', 9.7 , 1, NULL),
  (1, NULL, 'Prodotto 10', NULL, 10, 1, NULL),
  (1, 'decin', 'Prodotto 11', '1l', 11, 1, NULL),
  (1, 'decin', 'Prodotto 12', '2l', 12, 1, 'NON CI PROVARE'),
  (1, 'decin', 'Prodotto 13', '3l', 13.99, 1, NULL);

CREATE TABLE listino_6 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  categoria TEXT,
  disponibile INTEGER DEFAULT 1,
  descrizione_prodotto TEXT NOT NULL,
  dettaglio_qta TEXT,
  prezzo REAL NOT NULL,
  n_min_colli INTEGER NOT NULL DEFAULT 1,
  nota TEXT
);

CREATE TABLE ordine_in_corso_1 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti INTEGER NOT NULL,
  effettuato_il TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_1 (id)
);

CREATE TABLE ordine_in_corso_2 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti INTEGER NOT NULL,
  effettuato_il TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_2 (id)
);

CREATE TABLE ordine_in_corso_3 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti INTEGER NOT NULL,
  effettuato_il TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_3 (id)
);

CREATE TABLE ordine_in_corso_4 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti INTEGER NOT NULL,
  effettuato_il TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_4 (id)
);

CREATE TABLE ordine_in_corso_5 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti INTEGER NOT NULL,
  -- Utilizzato per priorità ?
  effettuato_il TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_utente) REFERENCES utenti (id),
  FOREIGN KEY (id_prodotto) REFERENCES listino_5 (id)
);

CREATE TABLE ordine_in_corso_6 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  id_utente INTEGER NOT NULL,
  id_prodotto INTEGER NOT NULL,
  colli_richiesti INTEGER NOT NULL,
  effettuato_il TEXT DEFAULT CURRENT_TIMESTAMP,
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
  (5, '2020-08-09', '2020-10-21', NULL, 0);

-- Le rettifiche presenti nei movimenti, sono da considerare solo nel caso un
-- referente si sbagli durante la fase di chiusura di un ordine, in cui viene
-- sistemato l'importo di acquisto corretto (dal referente una volta consegnato)
-- + gestore: CHI ha effettuato il movimento, nel caso degli acquisti, sarà
-- l'applicativo, quindi per convenzione, id 0 (vedi DEFAULT in CREATE TABLE)
-- + tipologia: vedi tabella tipologie_movimenti, inserito l'ID
insert into movimenti
(per_id_utente, verso_id, gestore, tipologia, effettuato_il, importo)
values
  (1,1,5,1,'2019-02-12','100'),
  (2,2,5,1,'2019-03-12','80'),
  (3,3,5,1,'2019-04-12','40'),
  (5,5,5,1,'2019-05-12','20'),
  (2,2,5,2,'2020-02-12','-10'),
  (2,2,5,2,'2020-03-12','-15'),
  (1,2,5,3,'2020-04-12','-20'),
  (2,2,5,3,'2020-04-12','20'),
  (1,1,0,4,'2021-12-12','10'),
  (2,1,0,4,'2021-11-12','10'),
  (3,1,0,4,'2021-11-12','10'),
  (5,1,0,4,'2021-11-12','10');

