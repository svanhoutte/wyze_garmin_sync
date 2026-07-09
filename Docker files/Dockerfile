FROM python:3.12-alpine
LABEL maintainer="Sebastien Vanhoutte"
RUN apk add --no-cache ca-certificates uv && update-ca-certificates
RUN uv add wyze_sdk garth
RUN mkdir /wyze_garmin_sync
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
WORKDIR /wyze_garmin_sync
COPY ./*.py /wyze_garmin_sync
COPY ./entrypoint.sh /usr/bin/
RUN chmod +x /usr/bin/entrypoint.sh
CMD /bin/sh /usr/bin/entrypoint.sh
