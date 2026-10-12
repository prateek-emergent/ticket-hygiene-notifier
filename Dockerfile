# Ticket-hygiene notifier: one container runs the notifier, the dashboard and the down-alert watchdog
# (docker/start.sh). Secrets come from the environment (the platform's secret settings, or --env-file .env);
# state.db lives in the /data volume so alert history survives restarts and redeploys.
#
#   docker build -t ticket-hygiene .
#   docker run -d --name ticket-hygiene --env-file .env -v ticket-hygiene-data:/data -p 127.0.0.1:8090:8090 ticket-hygiene
#
# Run ONE container only: two notifiers would post every alert twice.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATE_DB=/data/state.db \
    DASHBOARD_HOST=0.0.0.0 \
    NOTIFIER_MODE=run

# tini: stops all three processes cleanly on `docker stop`.
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# What is copied is decided by .dockerignore: code, config.py, config/, kb/, the roster, the built dashboard.
COPY . .

RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
USER app
VOLUME /data

# 8090: dashboard. 8080: Trinity push endpoint, used only with NOTIFIER_MODE=serve.
EXPOSE 8090 8080

# Unhealthy when the notifier's heartbeat is older than 5 min (crashed or hung).
HEALTHCHECK --interval=1m --timeout=15s --start-period=5m --retries=3 CMD ["python", "-m", "notifier", "health"]

ENTRYPOINT ["tini", "-g", "--"]
CMD ["sh", "docker/start.sh"]
