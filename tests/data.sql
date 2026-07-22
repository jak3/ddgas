insert into utenti (username, password, email)
values
  ('user1', 'pbkdf2:sha256:150000$M3fEKsQ8$2bdef2a755bfe8be21e6c97512fffcc0dc58b9878470f0ba38ff6618c3bf0752', 'user1@gmail.com'),
  ('user2', 'pbkdf2:sha256:150000$iEL42DFm$02d779bca75655ab84231d8ed890ddfd5e19d2c8c62cdac5fe9bd577de548b84', 'user2@gmail.com'),
  ('user3', 'pbkdf2:sha256:150000$mBLIsbKG$7bb9940840d0044b5f52897b6532afaee371b0ec2727189820ea07602a659327', 'user3@gmail.com'),
  ('user4', 'pbkdf2:sha256:150000$fL2T7W6M$a9729f3dd93e40b987938e4ace131c2abde2112e61b0e6bee19fe66cad7fd4d0', 'user4@gmail.com'),
  ('user5', 'pbkdf2:sha256:150000$Mn3PFLq9$fc741b8049677adc60df72b1d1c6257c14110eb78187900e1985b4fc1e91e411', 'user5@gmail.com');

insert into produttori (id_utente, nome, descrizione)
values
  (1, 'produttore1', 'Verdura e Frutta'),
  (2, 'produttore2', 'Verdura e Frutta'),
  (3, 'produttore3', 'Verdura e Frutta'),
  (4, 'produttore4', 'Verdura e Frutta'),
  (5, 'produttore5', 'Verdura e Frutta');
