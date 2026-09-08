# DDGAS — Sito Web per Gruppi di Acquisto Solidale

Applicazione generica per la gestione di un GAS (produttori, ordini, cassa
condivisa, ricariche), personalizzabile per associazione tramite
`config/associazione.yaml`.

## Sei un GAS e vuoi capire se fa per te?

- **[docs/panoramica.md](docs/panoramica.md)** — cosa offre e cosa serve
  per adottarlo (conto corrente dedicato, un referente, hosting).
- **[docs/casi-duso.md](docs/casi-duso.md)** — chi lo usa già, con numeri
  reali: non è un prototipo.
- Il resto della documentazione funzionale (produttori/listini, ordini,
  portafoglio, comunità, stampe) è linkato da `panoramica.md`, un file
  per area.

### Contatti

- **giacomo.mantani@studio.unibo.it** — sviluppatore e manutentore di
  DDGAS, per domande sul software o per attivare una nuova istanza per
  il tuo GAS.
- **malatech@googlegroups.com** — il gruppo tecnico del GAS Malatesta
  (il caso d'uso descritto in `casi-duso.md`), per domande più operative
  su come lo usiamo noi.
- **infogas@googlegroups.com** — contatto generale del GAS Malatesta.

## Attivare una nuova istanza

Vedi [`ONBOARDING.md`](ONBOARDING.md) per la checklist di configurazione
per una nuova associazione.

## Sviluppo

Vedi [`DEV.md`](DEV.md).

- Framework: [flask](https://flask.palletsprojects.com)
  - Template Engine [Jinja](https://jinja.palletsprojects.com)
- CSS: [turretcss](https://turretcss.com)

### Init Project

```
source env/bin/activate
flask init-db
flask run
```
