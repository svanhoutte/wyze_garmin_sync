FROM python:3.12-alpine
LABEL maintainer="Sebastien Vanhoutte"
RUN apk add --no-cache ca-certificates uv curl openssl
RUN curl -sL https://cacerts.digicert.com/DigiCertGlobalRootCA.crt -o DigiCertGlobalRootCA_raw.crt
RUN openssl x509 -inform der -in DigiCertGlobalRootCA_raw.crt -out DigiCertGlobalRootCA.crt
RUN mkdir -p /usr/local/share/ca-certificates/
RUN cp DigiCertGlobalRootCA.crt /usr/local/share/ca-certificates/DigiCertGlobalRootCA.crt
RUN update-ca-certificates
RUN uv pip install --system wyze_sdk garth 
RUN mkdir /wyze_garmin_sync
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
WORKDIR /wyze_garmin_sync
COPY ./*.py /wyze_garmin_sync
COPY ./entrypoint.sh /usr/bin/
RUN chmod +x /usr/bin/entrypoint.sh
CMD /bin/sh /usr/bin/entrypoint.sh
