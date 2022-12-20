FROM ubuntu:latest
MAINTAINER Sebastien Vanhoutte
RUN apt-get update && apt-get -y upgrade && apt-get install -y python3 default-jre unzip python3-pip apt-utils build-essential software-properties-common byobu curl git htop man unzip vim wget libcairo2 libcairo2-dev libgirepository1.0-dev libpython3-dev meson ninja-build patchelf cmake libdbus-1-dev libgirepository1.0-dev libcairo2-dev git cron
RUN pip3 list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 | xargs -n1 pip3 install -U
RUN pip3 install wyze_sdk garmin-uploader
RUN mkdir /wyze_garmin_sync
WORKDIR /
RUN git clone https://github.com/svanhoutte/wyze_garmin_sync.git
WORKDIR /wyze_garmin_sync
ADD garmin_wyze_scheduler /etc/cron.d/
RUN chmod 0644 /etc/cron.d/garmin_wyze_scheduler && crontab /etc/cron.d/garmin_wyze_scheduler
ADD entrypoint.sh ./
CMD /wyze_garmin_sync/entrypoint.sh

