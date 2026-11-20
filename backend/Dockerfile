# Chikka Reborn API. Build context: backend/.  See docs/deployment/deployment-guide.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Dependencies first so code changes reuse the cached layer. Versions are pinned in the file.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Run as an unprivileged user.
RUN useradd --system --uid 10001 --no-create-home chikka
USER chikka

# The platform injects PORT. FORWARDED_ALLOW_IPS must name the platform's proxy addresses
# (see the deployment guide); uvicorn only trusts X-Forwarded-For from those.
ENV PORT=8000 \
    FORWARDED_ALLOW_IPS=127.0.0.1
EXPOSE 8000

# Liveness only (no database call). Readiness is /readyz and belongs to the platform probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/healthz' % os.environ['PORT'], timeout=4)"

# One process on purpose: the SMS worker, notification worker, presence and WebSocket hub live
# in memory (docs/deployment/sms-live-activation.md, "Known limitations"). Scale up, not out.
# The preflight refuses to start the server with an unsafe hosted configuration.
CMD ["sh", "-c", "python -m app.preflight && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --no-server-header --timeout-graceful-shutdown 20"]
