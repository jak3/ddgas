# DDGAS — Sito Web per Gruppi di Acquisto Solidale

Applicazione generica per la gestione di un GAS (produttori, ordini, cassa
condivisa, ricariche), personalizzabile per associazione tramite
`config/associazione.yaml`. Per attivare una nuova istanza vedi
[`ONBOARDING.md`](ONBOARDING.md); per lo sviluppo vedi [`DEV.md`](DEV.md).

- Framework: [flask](https://flask.palletsprojects.com)
  - Template Engine [Jinja](https://jinja.palletsprojects.com)
- CSS: [turretcss](https://turretcss.com)

### Init Project

```
source env/bin/activate
flask init-db
flask run
```
