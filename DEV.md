# TO DO

## Fixes

- SINGLE_LINE_STRING in model.checks permette stringhe vuote, disabilitare?
- gestire tutte le date (scadenza e consegna) con `timestamp` 'with timezone'

## Nuove Funzionalità

## Controller / Python

- Uniformare e formattare codice
- Funzione di utilizzo per column_names, placeholders
- auth/tesseramenti necessita di una modalità per pulire tutte le sessioni
  utente create fino ad ora, in modo da forzare il login. Al momento l'unica
  soluzione trovata è [cambiare la SECRET_KEY](https://stackoverflow.com/questions/14737531/how-to-i-delete-all-flask-sessions)
  app.secret_key = os.urandom(32)

## View / HTML

- Uniformare e formattare codice
- Uniformare movimenti/list e movimenti/list_all (il codice Ereditarietà)
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
