FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system veda \
    && useradd --system --gid veda --create-home --home-dir /home/veda veda

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/
COPY deploy/entrypoint-api.sh /entrypoint-api.sh
RUN sed -i 's/\r$//' /entrypoint-api.sh \
    && chmod +x /entrypoint-api.sh \
    && chown -R veda:veda /app /entrypoint-api.sh

USER veda
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=8 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["/entrypoint-api.sh"]
