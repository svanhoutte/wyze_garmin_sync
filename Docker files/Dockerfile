FROM python:alpine
LABEL maintainer="Sebastien Vanhoutte"
RUN apk add --no-cache ca-certificates && update-ca-certificates
RUN pip install wyze_sdk garth
RUN mkdir /wyze_garmin_sync
WORKDIR /wyze_garmin_sync
COPY ./*.py /wyze_garmin_sync
COPY ./entrypoint.sh /usr/bin/
RUN chmod +x /usr/bin/entrypoint.sh
CMD /bin/sh /usr/bin/entrypoint.sh
