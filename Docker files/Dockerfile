FROM python:3.12-alpine

LABEL maintainer="Sebastien Vanhoutte"

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

RUN apk add --no-cache ca-certificates uv \
    && apk add --no-cache --virtual .cert-deps curl openssl \
    && curl -fsSL https://cacerts.digicert.com/DigiCertGlobalRootCA.crt -o /tmp/DigiCertGlobalRootCA_raw.crt \
    && openssl x509 -inform der -in /tmp/DigiCertGlobalRootCA_raw.crt -out /usr/local/share/ca-certificates/DigiCertGlobalRootCA.crt \
    && update-ca-certificates \
    && rm -f /tmp/DigiCertGlobalRootCA_raw.crt \
    && apk del .cert-deps

WORKDIR /wyze_garmin_sync

COPY requirements.txt ./
RUN uv pip install --system --no-cache wyze_sdk garth

COPY *.py ./
COPY entrypoint.sh /usr/bin/entrypoint.sh

RUN chmod +x /usr/bin/entrypoint.sh

ENTRYPOINT ["/bin/sh", "/usr/bin/entrypoint.sh"]

