# syntax=docker/dockerfile:1
FROM python:3.15-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first for layer caching.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application code + public config + participant-visible dataset.
# NOTE: config/ground_truth.yaml is intentionally NOT copied into the image for
# production builds — see .dockerignore. In development it is mounted read-only
# by docker-compose so the standalone validator can score answers.
COPY app/ /app/app/
COPY config/challenge.yaml /app/config/challenge.yaml
COPY config/tasks.yaml /app/config/tasks.yaml
COPY dataset/ /app/dataset/

# Run as non-root.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Honor a platform-injected $PORT (e.g. ngelinx) and default to 8080 otherwise.
HEALTHCHECK --interval=20s --timeout=5s --retries=3 --start-period=10s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.getenv('PORT','8080'), timeout=2)" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
