FROM python:3.10-alpine@sha256:8ca9f9d0f4df2af674092e7e9d79ce7985e783cecfe070f8ea850801b6520bf7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ONLY_BINARY=:all:

WORKDIR /app

COPY pip-bootstrap.lock requirements.lock ./
RUN apk upgrade --no-cache \
    && python -m pip install --no-cache-dir --require-hashes -r pip-bootstrap.lock \
    && python -m pip install --require-hashes -r requirements.lock \
    && rm -rf /usr/local/lib/python3.10/site-packages/pip \
        /usr/local/lib/python3.10/site-packages/pip-*.dist-info \
        /usr/local/lib/python3.10/ensurepip \
        /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.10

COPY manage.py ./manage.py
COPY accounts/ ./accounts/
COPY attendance/ ./attendance/
COPY config/ ./config/
COPY employees/ ./employees/
COPY holidays/ ./holidays/
COPY hr_copilot/ ./hr_copilot/
COPY leave_management/ ./leave_management/
COPY notifications/ ./notifications/
COPY system_logs/ ./system_logs/

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh \
    && chmod 0755 /entrypoint.sh \
    && install -d -o nobody -g nobody -m 0700 /home/app \
    && mkdir -p /app/media \
    && chown nobody:nogroup /app/media

ENV HOME=/home/app

USER nobody:nobody

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3)"]

ENTRYPOINT ["/entrypoint.sh"]
