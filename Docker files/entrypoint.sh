#!/bin/sh
set -e

SCRIPT="/wyze_garmin_sync/scale.py"
CRONTAB_DIR="/var/spool/cron/crontabs"
CRONTAB_FILE="${CRONTAB_DIR}/root"

chmod 0770 "$SCRIPT"

#
# ------------------------------------------------------------
# Command-line / one-shot mode
# ------------------------------------------------------------
#
# If arguments are supplied to the container, run scale.py once
# with those arguments and exit.
#
# Example:
#
# docker compose run --rm wyzegarminconnect \
#   -timewindow "2026-01-01" "2026-09-30"
#
if [ "$#" -gt 0 ]; then
    exec "$SCRIPT" "$@"
fi


#
# ------------------------------------------------------------
# Normal scheduled mode
# ------------------------------------------------------------
#

echo "Starting Wyze Garmin Sync scheduler"

mkdir -p "$CRONTAB_DIR"

#
# BusyBox crond inherits the Docker container environment.
#
# Do NOT put WYZE_EMAIL, passwords, tokens, etc. into the
# crontab. BusyBox crond does not support arbitrary environment
# assignments in the crontab itself.
#
cat > "$CRONTAB_FILE" <<EOF
PATH=$PATH
*/10 * * * * { printf "%s: " "\$(date "+\%F \%T")"; $SCRIPT; } >/proc/1/fd/1 2>/proc/1/fd/2
EOF

chmod 0600 "$CRONTAB_FILE"


#
# Show the installed schedule in the Docker log.
#
echo "Installed cron schedule:"
cat "$CRONTAB_FILE"

echo
echo "Running initial synchronization..."
"$SCRIPT"

echo
echo "Initial synchronization complete."
echo "Starting cron scheduler - synchronization will run every 10 minutes."
echo


#
# Run BusyBox crond in foreground.
#
# -f = foreground
# -d = log directly to stderr rather than syslog
#
exec crond -f -d 6
