# FLOW Web: só telas (sem banco). Os dados vêm das APIs, chamadas pelo navegador.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8002
CMD ["gunicorn", "frontend.wsgi:application", "--bind", "0.0.0.0:8002", "--workers", "2"]
