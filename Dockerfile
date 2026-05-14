FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DB_PATH=/data/eurovision.db

WORKDIR /app

RUN groupadd --system --gid 1001 bot \
    && useradd --system --uid 1001 --gid bot --home-dir /app --shell /usr/sbin/nologin bot \
    && mkdir -p /data \
    && chown -R bot:bot /app /data

COPY --chown=bot:bot requirements.txt ./
RUN pip install -r requirements.txt

COPY --chown=bot:bot bot.py data.py ./

USER bot

VOLUME ["/data"]

CMD ["python", "-u", "bot.py"]
