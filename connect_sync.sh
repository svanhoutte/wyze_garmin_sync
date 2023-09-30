#!/bin/bash
#WYZE_EMAIL=youremail
#WYZE_PASSWORD=yourpassword
#Garmin_username=youremail
#Garmin_password=yourpassword
#export WYZE_EMAIL
#export WYZE_PASSWORD
#cd /path_to_yourscript/
pushd /wyze_garmin_sync/
python3 /wyze_garmin_sync/scale.py
if md5sum -c /wyze_garmin_sync/cksum.txt; then
echo "no new measurment"
exit 0
else
if python3 ./2FA.py ./wyze_scale.fit; then
echo "file uploaded"
md5sum /wyze_garmin_sync/wyze_scale.fit > /wyze_garmin_sync/cksum.txt
exit 0
else
echo "file not uploaded"
fi
fi
exit 0


