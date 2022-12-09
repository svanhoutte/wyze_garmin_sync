# wyze_garmin_sync
Scale sync between Wyze Scale and Garmin connect

This is a script shell allowing you to leverage  [Garmin-uploader](https://github.com/La0/garmin-uploader),[Wyze_SDK](https://github.com/shauntarves/wyze-sdk) and [Garmin Fit SDK](https://developer.garmin.com/fit/fitcsvtool/) fitcsvtool to autoamtically upload the last measure on your Wyze Smart scale in Garmin Connect.

In the new version the 2FA has been added, as well as the autodiscovery of the scale. Additionally in order to make portability and install more plug and play, the whole solution is now available through docker.

## 2FA requirements / TOTP

wyze_sdk implemented support for using TOTP (Time-Based One-Time Password).

How to Setup TOTP
If you already have 2FA setup on your Wyze account you will have to reapply iy, you will have to remove it and readd it.
To remove it, navigate to the Wyze app and go - Accounts -> Security -> Two-Factor Authentication and remove verification
Back in Accounts -> Security -> Two-Factor Authentication, select Verification by Authenticator app.
Read the instructions from Wyze BUT make sure to copy and KEEP the value in step 3. This is your Base32 SECRET used to generate TOTP.
Go ahead and setup your TOTP on the Authenticator of your choosing.
Edit the file to fill in the environment variable username, password and for TOTP, copy the Base32 SECRET you got from the Wyze app
Submit and you should now be authenticated with 2FA enabled!

## Install through docker compose (recommended)

Download the docker-compose.yml and add your credentials:

```bash
version: "3.9"
services:
  wyzegarminconnect:
    image: svanhoutte/wyzegarminconnect:latest
    restart: unless-stopped
    network_mode: "host"
    environment:
      WYZE_EMAIL: "wyze username"
      WYZE_PASSWORD: "wyze password"
      WYZE_TOTP: "wyze totp cf § how to setup totp"
      Garmin_username: "garmin username"
      Garmin_password: "garmin password"
    volumes:
      - "/etc/timezone:/etc/timezone:ro"
      - "/etc/localtime:/etc/localtime:ro"
```

The volumes are mounted to sync logs in the containers and the host. 

## Legacy install 

### Requirements

This requires Python 3.8 and above. If you're unsure how to check what version of Python you're on, you can check it using the following:

> **Note:** You may need to use `python3` before your commands to ensure you use the correct Python path. e.g. `python3 --version`

```bash
python --version

-- or --

python3 --version
```
You ll need to have also Java8 or 1.8 installed (oracle or open java are working fine)

```bash
java -version

```
You ll need also a linux environment mine is an Ubuntu 20.04.2 but most of the recent distrib should work.

### Installation

#### Installation of Wyze SDK

```bash
$ pip install wyze_sdk
```
#### Installation of Garmin-uploader

```bash
$ pip install garmin-uploader
```

#### Installation of Garmin Fit SDK

I recommend you put yourslef in a specific directory
```bash
wget https://developer.garmin.com/downloads/fit/sdk/FitSDKRelease_21.94.00.zip
unzip FitSDKRelease_21.94.00.zip
```

#### Installation of the script shell

Edit the script shell connect_sync.legacy.sh to enter your credentials.

```bash
WYZE_EMAIL=
WYZE_PASSWORD=
WYZE_TOTP=
Garmin_username=
Garmin_password=
```
Edit the script to enter the path of the FitCSVTool.jar program

#### Installation of the python script

The script scale.py will query the scale now automatically (caveats will work only for 1 scale). If this doesn't work please use the mac_address_devices.py as bellow. 
To discover the mac address rune the script mac_address_devices.py.

```bash
WYZE_EMAIL=
WYZE_PASSWORD=
WYZE_TOTP=
export WYZE_EMAIL
export WYZE_PASSWORD
export WYZE_TOTP
python3 ./mac_address_devices.py
```
the script should load all the wyze devices attached to your profile such as below

```bash
product model: WYZECP1_JEF
mac: JA.SC.XXXXXXXXXXXX
nickname: Wyze Scale
is_online: True
product model: JA.SC
```
Take the mac address and edit scale.py to add it like this
scale = client.scales.info(device_mac='**JA.SC.XXXXXXXXXXXX**')

#### Run the script

In your working directory run connect_sync.sh and if all goes well you should be able to see your data in garmin connect

#### Setup with Cron

Will run the script every 10 min to get if a new measurment has been made on the scale.

```bash
*/10 * * * * path_to_script/connect_sync.sh 2>&1 | /usr/bin/logger -t garminsync
```


