# TO DO

## Nuove Funzionalità

## View / HTML

- bottone "Vedi Contatti" in list_produttori da esplicitare un pochino di che
  contatto si tratta e renderlo visibilmente più carino

## Model

- ORM
- Aggiungere Tests
- Benchmark close connection/cursor pg
- [schema.sql] change ruoli.ruolo to ruoli.nome
- [schema.sql] arruolati.id_ruolo/.id_utente UNIQUE?
- [schema.sql] fare in modo che sia richiesto un utente fondo cassa per poter
  utilizzare movimenti di aggiusta_ordine_chiuso

## Security

- check [template injection](https://github.com/epinna/tplmap)
  [blog post](http://ha.cker.info/exploitation-of-server-side-template-injection-with-craft-cms-plguin-seomatic/)

# Useful Functions

SQLite:

```
dbi.set_trace_callback(print)
```
PG:

`print(dbi.query)`

or

```
>>> cur.mogrify("INSERT INTO test (num, data) VALUES (%s, %s)", (42, 'bar'))
"INSERT INTO test (num, data) VALUES (42, E'bar')"
```

# Environment

Python 3 (issues with python 2)

```
export FLASK_APP="delek:create_app(True)"
export DATABASE_URL=delek
export SECRET_KEY=dev

source env/bin/activate
flask run
```

## Formattazione (black)

`black` è nei requirements-dev. Config in `pyproject.toml`
(`skip-string-normalization = true`: il codice usa apici singoli in modo
già coerente, non ha senso che black li converta tutti in doppi — evita
un diff enorme che sarebbe solo rumore). Solo Python: i template Jinja
non hanno un formatter automatico maturo/sicuro (rischio di rompere
whitespace dentro `<pre>` o espressioni multi-riga), lì si ripulisce
manualmente quando si tocca un file per altri motivi.

```
black delek tests
black --check delek tests  # solo verifica, non modifica
```

## Docker (ambiente locale)

Alternativa a Postgres installato nativamente (vedi sezione PG sotto, che
su alcune distro richiede build da sorgente): `docker-compose.yml` avvia
app + Postgres già inizializzato con schema e dati di test.

```
docker compose up
docker compose exec app flask create-admin
```

Il DB è già popolato da `data/db/pg/dev_data.sql` (utenti di test
mode/refe/teso/..., alcuni produttori). `docker compose down -v` cancella
il volume e riparte da zero alla `up` successiva. Per lanciare i test
dentro il container: `docker compose exec -e DELEK_DB_HOST=db app python -m pytest`.

Pensato solo per sviluppo/test locale, non per il deploy in produzione
(quello resta Heroku, vedi sotto — valutare un'immagine di produzione è
un lavoro separato, non ancora fatto).

## Tesseramenti: blocco continuo, non solo al login

Quando parte una nuova campagna tesseramenti, chi era già loggato prima
non va ri-autenticato: `auth.load_logged_in_user()` (before_app_request)
rivaluta `is_tesserato()` ad ogni richiesta, non solo al momento del
login. Un utente non più in regola viene bloccato sulla pagina di
adesione tesseramento alla richiesta successiva, con la sessione ancora
valida (nessun logout forzato, nessuna rotazione di SECRET_KEY). Endpoint
esenti (altrimenti redirect loop): `ENDPOINT_ESENTI_DA_TESSERAMENTO` in
`delek/controller/auth.py`.

## Fuso orario (scadenza, consegna, ecc)

Tutte le colonne data sono `TIMESTAMPTZ`. `delek.controller.db.get_db()`
imposta `SET TIME ZONE 'Europe/Rome'` su ogni connessione, quindi
`CURRENT_TIMESTAMP`/`now()` lato Postgres sono già in ora italiana
indipendentemente dal fuso del server (es. UTC su Heroku). Lato Python, usa
sempre `delek.controller.tempo.adesso()` invece di `datetime.now()`/
`datetime.today()`, e `tempo.da_form(...)` invece di
`datetime.fromisoformat(...)` per i valori letti da form: entrambe
ritornano `datetime` "aware" ancorati a Europe/Rome, indispensabile per
confrontarli con i valori (ora aware) letti dal DB senza sollevare
`TypeError`.

## Ricariche (Stripe, Satispay)

Il blueprint `pagamenti` (`delek/controller/pagamenti.py`) viene registrato
solo se `STRIPE_SECRET_KEY` è impostata (`PAGAMENTI_ABILITATI`): finché non
è configurata, la voce Ricarica sparisce dalla UI invece di rompere ogni
pagina con un BuildError su `url_for('pagamenti.*')`.

Variabili d'ambiente richieste per Stripe:

```
export STRIPE_SECRET_KEY=sk_test_...
export STRIPE_WEBHOOK_SECRET=whsec_...
```

Entrambe si trovano nella dashboard Stripe (modalità Test per lo sviluppo).
Il webhook secret è specifico dell'endpoint configurato in Stripe > Developers
> Webhooks, puntato su `/pagamenti/webhook/stripe`; in locale, per riceverlo,
serve un tunnel (es. `stripe listen --forward-to localhost:5000/pagamenti/webhook/stripe`
con la Stripe CLI, che stampa il webhook secret da usare).

Satispay è un metodo aggiuntivo, condivide lo stesso blueprint ma ha un
flag separato (`SATISPAY_ABILITATO`) perché può essere pronto in un momento
diverso da Stripe:

```
export SATISPAY_KEY_ID=...
export SATISPAY_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----..."
# opzionale, default punta all'ambiente di produzione Satispay:
export SATISPAY_BASE_URL=https://staging.authservices.satispay.com/g_business/v1
```

Si ottengono scambiando una chiave RSA generata da noi con il codice di
attivazione (dashboard Satispay) via `POST /authentication_keys` — vedi
https://developers.satispay.com/docs/authentication. La callback S2S di
Satispay (`/pagamenti/webhook/satispay`) non è raggiungibile da un tunnel
verso `127.0.0.1`: per testarla in locale va simulata a mano (GET con
`?payment_id=...`) dopo aver creato un pagamento vero in sandbox.

## PG

```
initdb -D /usr/local/pgsql/instance --locale=it_IT.UTF-8 -E UTF8
pg_ctl -D /usr/local/pgsql/instance -l /usr/local/pgsql/logfile start
createdb delek
psql delek -f schema.sql
psql delek -f dev.sql
python load.py
psql -h localhost delek
```

## Heroku

[config vars](https://devcenter.heroku.com/articles/config-vars#using-foreman)
```
heroku login
  heroku config:set FLASK_APP=delek
  heroku config:set FLASK_ENV=development
  heroky config:set SECRET_KEY='LOLLIPOP;)IAMNOTTHEREALKEY'
heroku config:set WEB_CONCURRENCY=3
heroku pg:psql
heroku pg:reset DATABASE
heroku pg:push delek DATABASE_URL --app gasma-test
```
```
heroku local web
heroku open
heroku run CMD
heroku addons
heroku config
heroku pg
heroku web
heroku logs
heroku logs -p postgres -t
```

```bash
heroku login
git push heroku master
```

` heroku[router]: at=error code=H10 desc="App crashed" ` is always something
missing in `Procfile` (have you installed all dependencies in `requirements.txt`?)

Download current DB to live test error in local env:

```bash
heroku pg:backups:capture
heroku pg:backups:download
  out| latest.dump
heroku config:get DATABASE_URL
  out| 'postgres://xbswtmslnjjeqj...'
heroku pg:backups:schedule --at '02:00 Europe/Rome'
# REQUIRE same version of pg_restore remote/local LOCALDB = delek
pg_restore --verbose --clean --no-acl --no-owner -d LOCALDB latest.dump
# local dump
pg_dump -Fp --no-acl --format=c --no-owner delek > current-dev.dump
# remote restore
heroku pg:backups:restore 'https://www.dropbox.com/scl/fi/lmonj4qs2u8t8i1p52q82/latest.dump?rlkey=0oycnepyvnmmks5m2wr7plxwa&raw=1' DATABASE_URL --app gasma
```

Slackware Hints to Build newer PG version:

```bash
wget https://ftp.postgresql.org/pub/source/v13.5/postgresql-13.5.tar.bz2
tar xvfj postgresql-13.5.tar.bz2
cd postgresql-13.5
./configure --prefix=/usr/lib64/postgresql/13.5 --sysconfdir=/etc/postgresql/13.5 --includedir=/usr/include --datarootdir=/usr/share --mandir=/usr/man --docdir=/usr/doc/postgresql-13.5 --datadir=/usr/share/postgresql-13.5 --with-openssl --with-tcl --with-python --with-libxml --with-libxslt --enable-thread-safety --with-system-tzdata=/usr/share/zoneinfo --build=x86_64-slackware-linux
make
make install-strip DESTDIR=/opt/postgresql/
make install-docs DESTDIR=/opt/postgresql/
```

# Docs

- [Flask User Guide](https://flask.palletsprojects.com)
- [werkzeug](https://werkzeug.palletsprojects.com)
- [jinja](https://jinja.palletsprojects.com)
- [turretcss](https://turretcss.com/)
