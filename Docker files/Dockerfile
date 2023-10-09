FROM python:slim-bullseye
MAINTAINER Sebastien Vanhoutte
RUN apt-get update &&  apt-get install --no-install-recommends -y gcc git cron libc6-dev
RUN pip install wyze_sdk garth
RUN mkdir /wyze_garmin_sync
WORKDIR /
RUN git clone https://github.com/svanhoutte/wyze_garmin_sync.git
WORKDIR /wyze_garmin_sync
RUN apt-get remove -y gcc git libc6-dev
ADD entrypoint.sh ./
RUN chmod +x ./entrypoint.sh
CMD /wyze_garmin_sync/entrypoint.sh
FROM python:alpine3.18
MAINTAINER Sebastien Vanhoutte
#RUN apt-get update &&  apt-get install --no-install-recommends -y gcc git cron libc6-dev
RUN apk add git bash rust gcc curl cargo
RUN pip install wyze_sdk garth
RUN mkdir /wyze_garmin_sync
WORKDIR /
RUN git clone https://github.com/svanhoutte/wyze_garmin_sync.git
WORKDIR /wyze_garmin_sync
#RUN apt-get remove -y gcc git libc6-dev
RUN apk del rust gcc curl cargo git
COPY entrypoint.sh /usr/bin/
RUN chmod +x /usr/bin/entrypoint.sh
CMD /usr/bin/entrypoint.sh
