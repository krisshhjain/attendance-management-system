FROM python:3.10-slim@sha256:6ff506466f8b1e981719b468cc0023b8ef000b983cdec0eafe119d01f379e31d

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ONLY_BINARY=:all:

WORKDIR /app

COPY pip-bootstrap.lock requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r pip-bootstrap.lock \
    && python -m pip install --require-hashes -r requirements.lock

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
    && mkdir -p /app/media \
    && chown nobody:nogroup /app/media

USER nobody:nogroup

ENTRYPOINT ["/entrypoint.sh"]
