# Immagine per lo sviluppo/test locale (docker-compose.yml). Non pensata
# per la produzione: installa anche le dipendenze di test e gira con
# `flask run --debug` (reload automatico, nessun worker gunicorn).
FROM python:3.12-slim

WORKDIR /app

# build-essential/libpq-dev servono a compilare psycopg2 da sorgente (in
# requirements.txt non è la variante -binary, sconsigliata in produzione):
# qui va bene comunque, è un'immagine solo per sviluppo/test.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0", "--debug"]
