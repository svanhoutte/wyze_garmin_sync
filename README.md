# Wyze Connect Sync
***

<p align="center">
  <img width="25%" src="https://user-images.githubusercontent.com/22617546/208175452-dbbff5b9-59ce-4ffc-a255-698617c94de0.jpg" />
</p>

[![Stars](https://img.shields.io/github/stars/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/stargazers)
[![Version](https://img.shields.io/github/v/release/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/releases/latest)
[![Commits Since Latest Release](https://img.shields.io/github/commits-since/svanhoutte/wyze_garmin_sync/latest)](https://github.com/svanhoutte/wyze_garmin_sync/commits/master)
[![Latest Release Date](https://img.shields.io/github/release-date/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/releases/latest)
[![Open Issues](https://img.shields.io/github/issues-raw/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/issues?q=is%3Aopen+is%3Aissue)
[![Closed Issues](https://img.shields.io/github/issues-closed-raw/svanhoutte/wyze_garmin_sync)](https://github.com/svanhoutte/wyze_garmin_sync/issues?q=is%3Aissue+is%3Aclosed)

[![PayPal](https://img.shields.io/badge/PayPal-Donate-green)](https://paypal.me/SVanhoutte79?country.x=US&locale.x=en_US)
[![Buymeacoffee](https://badgen.net/badge/icon/buymeacoffee?icon=buymeacoffee&label)](https://www.buymeacoffee.com/sebastienv)



***
**Sync the Wyze scale with Garmin connect**

The python script collect the data from your Wyze account and create the .fit file to be uploaded to Garmin. The script shell allows you to leverage  [Garmin-uploader](https://github.com/La0/garmin-uploader), and [Wyze_SDK](https://github.com/shauntarves/wyze-sdk) to automatically upload the last measurement you took on your Wyze smart scale to Garmin Connect.

The solution has been updated to support 2FA and now auto-discover the scale. 
Additionally in order to improve portability and have a more plug and play solution you can now enjoy a docker version

## Authentication 

Login/Pass/TOTP is not working anymore Wyze requires an API key and id to log in
Visit the Wyze developer API portal to generate an API ID/KEY: https://developer-api-console.wyze.com/#/apikey/view

## Install through docker compose

[![Docker](https://img.shields.io/docker/v/svanhoutte/wyzegarminconnect/latest?logo=docker)](https://hub.docker.com/repository/docker/svanhoutte/wyzegarminconnect)
![Docker](https://badgen.net/badge/color/arm64/yellow?icon=docker&label=) ![Docker](https://badgen.net/badge/color/arm/orange?icon=docker&label=) ![Docker](https://badgen.net/badge/color/amd64/blue?icon=docker&label=) 

Docker image is now available for amd64, arm64 and arm.

Download the [docker-compose.yml](https://github.com/svanhoutte/wyze_garmin_sync/blob/main/docker-compose.yml "docker-compose.yml") and add your credentials:

    version: "3.9"
    services:
      wyzegarminconnect:
        image: svanhoutte/wyzegarminconnect:latest
        restart: unless-stopped
        network_mode: "host"
        environment:
          WYZE_EMAIL: "wyze username"
          WYZE_PASSWORD: "wyze password"
          WYZE_KEY_ID: "ID"
	  WYZE_API_KEY: "KEY"
          Garmin_username: "garmin username"
          Garmin_password: "garmin password"
        volumes:
          - "/etc/timezone:/etc/timezone:ro"
          - "/etc/localtime:/etc/localtime:ro"

The volumes are mounted to sync logs in the containers and the host.
Then do the `docker compose up`


## Legacy install

### Requirements

This requires Python 3.8 and above. If you're unsure how to check what version of Python you're on, you can check it using the following:

> **Note:**  You may need to use  `python3`  before your commands to ensure you use the correct Python path. e.g.  `python3 --version`

    python --version
    
    -- or --
    
    python3 --version

You ll need also a linux environment most of the recent distribution should work.

### [](https://github.com/svanhoutte/wyze_garmin_sync#installation)Installation

#### [](https://github.com/svanhoutte/wyze_garmin_sync#installation-of-wyze-sdk)Installation of Wyze SDK

    $ pip install wyze_sdk

#### [](https://github.com/svanhoutte/wyze_garmin_sync#installation-of-garmin-uploader)Installation of Garmin-uploader

    $ pip install garmin-uploader

#### [](https://github.com/svanhoutte/wyze_garmin_sync#installation-of-the-script-shell)Installation of the script shell

First clone the repository 

    git clone https://github.com/svanhoutte/wyze_garmin_sync.git

Edit the script shell connect_sync.legacy.sh to enter your credentials.

    WYZE_EMAIL=
    WYZE_PASSWORD=
    WYZE_TOTP=
    WYZE_KEY_ID=
    WYZE_API_KEY=
    Garmin_username=
    Garmin_password=
	cd ~/path_to_your_script/

#### [](https://github.com/svanhoutte/wyze_garmin_sync#run-the-script)Run the script

In your working directory run connect_sync.legacy.sh and if all goes well you should be able to see your data in garmin connect

#### [](https://github.com/svanhoutte/wyze_garmin_sync#setup-with-cron)Setup with Cron

Will run the script every 10 min to get if a new measurment has been made on the scale.

    */10 * * * * path_to_script/connect_sync.legacy.sh 2>&1 | /usr/bin/logger -t garminsync

***
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/sebastienv)
