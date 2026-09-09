FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
RUN pip install --no-cache-dir .

EXPOSE 8000
# Migrations run inside the app on startup (ROCHADE_MIGRATE_ON_START).
# Behind Caddy (twice, in a deployment): trust the X-Forwarded-* headers so
# redirects and request.url carry the public scheme and host.
CMD ["uvicorn", "rochade.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
