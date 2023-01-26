#!/bin/bash
touch /etc/cron.d/garmin_wyze_scheduler
echo WYZE_EMAIL=$WYZE_EMAIL > /etc/cron.d/garmin_wyze_scheduler
echo WYZE_PASSWORD=$WYZE_PASSWORD >> /etc/cron.d/garmin_wyze_scheduler
echo WYZE_TOTP=$WYZE_TOTP >> /etc/cron.d/garmin_wyze_scheduler
echo Garmin_password=$Garmin_password >> /etc/cron.d/garmin_wyze_scheduler
echo Garmin_username=$Garmin_username >> /etc/cron.d/garmin_wyze_scheduler
echo "*/10 * * * * { printf \"\%s: \" \"\$(date \"+\%F \%T\")\"; /wyze_garmin_sync/connect_sync.sh ; } >/proc/1/fd/1 2>/proc/1/fd/2"
chmod 0644 /etc/cron.d/garmin_wyze_scheduler && crontab /etc/cron.d/garmin_wyze_scheduler
/bin/bash ./connect_sync.sh
cron -f
