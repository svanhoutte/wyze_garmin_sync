FROM python:3.12-alpine

LABEL maintainer="Sebastien Vanhoutte"

RUN apk add --no-cache ca-certificates && update-ca-certificates

RUN pip install --no-cache-dir \
    wyze_sdk \
    garminconnect==0.3.17

RUN mkdir -p /wyze_garmin_sync

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /wyze_garmin_sync

COPY ./*.py /wyze_garmin_sync/
COPY ./entrypoint.sh /usr/bin/entrypoint.sh

RUN chmod +x /usr/bin/entrypoint.sh \
    && chmod +x /wyze_garmin_sync/scale.py

ENTRYPOINT ["/usr/bin/entrypoint.sh"]
