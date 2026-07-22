-- nei movimenti avremo es:
-- versamento: (per_id_utente: N, verso_id: N)
-- prelievo: (per_id_utente: N, verso_id: N)
-- rettifica: (per_id_utente: N, verso_id: N)
-- giroconto: (per_id_utente: N, verso_id: M)
-- acquisto: (per_id_utente: N, verso_id: J)
-- rettifica: (per_id_utente: N, verso_id: J)
-- aggiustamento: (per_id_utente: J, verso_id: J)
-- dove N, M sono utenti.id, J è un produttori.id
-- quindi per versamento, prelievo, rettifica per_id_utente = verso_id
insert into tipologie_movimenti (id, nome)
values (1, 'versamento'), (2, 'prelievo'), (3, 'giroconto'), (4, 'acquisto'),
 (5, 'rettifica'), (6, 'aggiustamento'), (7, 'spese CC'), (8, 'spese varie');

insert into ruoli (ruolo, descrizione)
values
  ('moderatore', 'Aggiunge produttori, assegna referenti, gestisce i membri'),
  ('referente', 'Gestisce un produttore'),
  ('segretario', 'Si occupa dei verbali delle riunioni'),
  ('accoglienza', 'Introduce al gruppo i nuovi membri e li attiva agli acquisti'),
  ('tesoriere', 'Gestisce la cassa (versamenti e pagamenti annuali)'),
  ('tesseramenti', 'Avvia la campagna tesseramenti e può visionare i codice delle tessere ARCI'),
  ('presidiante', 'Assegna utenti per presidiare il ritiro'),
  ('produttore', 'Non paga la tessera annuale');


insert into arruolati (id_ruolo, id_utente)
values
  (1, 1), -- luigi moderatore
  (1, 63),-- manta moderatore
  (1, 51),-- GasMirco moderatore
  (5, 12) -- Cristinasi tesoriere
  ON CONFLICT DO NOTHING;
