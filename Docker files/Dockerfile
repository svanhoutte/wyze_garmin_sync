FROM python:3-slim
MAINTAINER Sebastien Vanhoutte
RUN if [ "$TARGETPLATFORM" = "linux/arm/v7" ]; then \
apt-get update &&  apt-get install --no-install-recommends -y gcc git cron libc6-dev \
RUN apt-get update &&  apt-get install --no-install-recommends -y git cron
RUN pip install wyze_sdk garth
RUN mkdir /wyze_garmin_sync
WORKDIR /
RUN git clone https://github.com/svanhoutte/wyze_garmin_sync.git
WORKDIR /wyze_garmin_sync
RUN apt-get remove -y gcc git libc6-dev
COPY entrypoint.sh /usr/bin/
RUN chmod +x /usr/bin/entrypoint.sh
CMD /usr/bin/entrypoint.sh
