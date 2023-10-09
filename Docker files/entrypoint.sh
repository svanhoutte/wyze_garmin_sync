#!/bin/bash
mkdir /etc/cron.d
touch /etc/cron.d/garmin_wyze_scheduler
echo PATH=$PATH > /etc/cron.d/garmin_wyze_scheduler
echo WYZE_EMAIL=$WYZE_EMAIL >> /etc/cron.d/garmin_wyze_scheduler
echo WYZE_PASSWORD=$WYZE_PASSWORD >> /etc/cron.d/garmin_wyze_scheduler
echo WYZE_KEY_ID=$WYZE_KEY_ID >> /etc/cron.d/garmin_wyze_scheduler
echo WYZE_API_KEY=$WYZE_API_KEY >> /etc/cron.d/garmin_wyze_scheduler
echo Garmin_password=$Garmin_password >> /etc/cron.d/garmin_wyze_scheduler
echo Garmin_username=$Garmin_username >> /etc/cron.d/garmin_wyze_scheduler
echo "*/10 * * * * { printf \"\%s: \" \"\$(date \"+\%F \%T\")\"; /wyze_garmin_sync/scale.py ; } >/proc/1/fd/1 2>/proc/1/fd/2" >> /etc/cron.d/garmin_wyze_scheduler
chmod 0644 /etc/cron.d/garmin_wyze_scheduler && crontab /etc/cron.d/garmin_wyze_scheduler
chmod 0770 /wyze_garmin_sync/scale.py
/bin/bash ./scale.py
crond -f
