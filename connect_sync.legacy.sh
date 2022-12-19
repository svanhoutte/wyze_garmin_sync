#!/bin/bash
# information to populate
WYZE_EMAIL=youremail
WYZE_PASSWORD=yourpassword
WYZE_TOTP=TOTP
Garmin_username=youremail
Garmin_password=yourpassword
export PATH="$HOME/.local/bin:$PATH"
export WYZE_EMAIL
export WYZE_PASSWORD
export WYZE_TOTP
cd ~/path_to_your_script/
# end of information to populate
python3 ./scale.py
if md5sum -c ./cksum.txt; then
echo "no new measurment"
exit 0
else
if gupload -u $Garmin_username -p $Garmin_password  -v 1 ./wyze_scale.fit; then
echo "file uploaded"
md5sum ./wyze_scale.fit > ./cksum.txt
exit 0
else
echo "file not uploaded"
fi
fi
exit 0

