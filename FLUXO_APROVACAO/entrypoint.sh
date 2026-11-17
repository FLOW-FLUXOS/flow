#!/bin/sh
set -e

# Espera o Postgres aceitar conexões
python - <<'PY'
import os, time, dj_database_url, psycopg
url = os.getenv("DATABASE_URL")
if url and url.startswith("postgres"):
    cfg = dj_database_url.parse(url)
    for i in range(30):
        try:
            psycopg.connect(dbname=cfg["NAME"], user=cfg["USER"], password=cfg["PASSWORD"],
                            host=cfg["HOST"], port=cfg["PORT"] or 5432).close()
            break
        except Exception:
            print("Aguardando o banco...", flush=True)
            time.sleep(2)
PY

# Só o container web aplica migrações e coleta os estáticos
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
fi

exec "$@"
