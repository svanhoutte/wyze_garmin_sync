#!/bin/sh
set -e

chmod 0770 /wyze_garmin_sync/scale.py

# If arguments were supplied to the container, run scale.py once with those
# arguments and exit. This enables:
#   docker compose run --rm wyzegarminconnect -timewindow "2026-01-01" "2026-09-30"
if [ "$#" -gt 0 ]; then
    exec /wyze_garmin_sync/scale.py "$@"
fi

mkdir -p /etc/cron.d
touch /etc/cron.d/garmin_wyze_scheduler

{
    echo "PATH=$PATH"
    echo "WYZE_EMAIL=${WYZE_EMAIL:-}"
    echo "WYZE_PASSWORD=${WYZE_PASSWORD:-}"
    echo "WYZE_KEY_ID=${WYZE_KEY_ID:-}"
    echo "WYZE_API_KEY=${WYZE_API_KEY:-}"
    echo "WYZE_TOKEN_FILE=${WYZE_TOKEN_FILE:-}"
    echo "token=${token:-}"
    echo "GARMIN_EMAIL=${GARMIN_EMAIL:-}"
    echo "GARMIN_PASSWORD=${GARMIN_PASSWORD:-}"
    echo "Garmin_username=${Garmin_username:-}"
    echo "Garmin_password=${Garmin_password:-}"
    echo "GARMINTOKENS=${GARMINTOKENS:-}"
    echo "BACKFILL_DELAY_SECONDS=${BACKFILL_DELAY_SECONDS:-1.0}"
    echo '*/10 * * * * { printf "%s: " "$(date "+%F %T")"; /wyze_garmin_sync/scale.py ; } >/proc/1/fd/1 2>/proc/1/fd/2'
} > /etc/cron.d/garmin_wyze_scheduler

chmod 0644 /etc/cron.d/garmin_wyze_scheduler
crontab /etc/cron.d/garmin_wyze_scheduler

# Normal container startup: run once immediately, then start the 10-minute cron.
/wyze_garmin_sync/scale.py
exec crond -f -l 8
