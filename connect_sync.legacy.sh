#!/bin/bash
WYZE_EMAIL=youremail
WYZE_PASSWORD=yourpassword
WYZE_TOTP=TOTP
Garmin_username=youremail
Garmin_password=yourpassword
export PATH="$HOME/.local/bin:$PATH"
export WYZE_EMAIL
export WYZE_PASSWORD
export WYZE_TOTP
cd ~/wyzetest/
python3 ./scale.py
if md5sum -c ./cksum.txt; then
echo "no new measurment"
exit 0
else
if gupload -u $Garmin_username -p $Garmin_password  -v 1 ./wyze_scale.fit; then
echo "file uploaded"
md5sum ./wyze_scale.fit > ./cksum.txt
else
echo "file not uploaded"
fi
fi
exit 0

