DROP TABLE IF EXISTS codici_arci;

CREATE TABLE codici_arci (
  id_utente INTEGER PRIMARY KEY,
  codice TEXT,
  FOREIGN KEY (id_utente) REFERENCES utenti (id) ON DELETE CASCADE
);
