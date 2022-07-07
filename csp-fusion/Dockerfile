FROM multirepo-oab.si.fr.intraorange:5002/library/python:3.9.6-slim-buster
LABEL maintainer="Fabrice Le Gallic"

WORKDIR /app
COPY fusion.py requirements.txt /app/

# Disable Artifactory certificate check by APT
RUN echo 'Acquire::https::multirepo-oab.si.fr.intraorange::Verify-Peer "false";' > /etc/apt/apt.conf.d/80ssl-exceptions \
    && echo 'Acquire::https::multirepo-oab.si.fr.intraorange::Verify-Host "false";' >> /etc/apt/apt.conf.d/80ssl-exceptions \
# Replace public Debian repositories by Artifactory repositories
    && sed -i "s/http:\/\/deb.debian.org\/debian/https:\/\/multirepo-oab.si.fr.intraorange\/debian-public/" /etc/apt/sources.list \
    && sed -i "s/http:\/\/security.debian.org/https:\/\/multirepo-oab.si.fr.intraorange/" /etc/apt/sources.list \
    && apt-get update && apt-get install -yq \
    ca-certificates \
    curl \
    && python3 -m pip install -r requirements.txt \
    && curl -sSL http://pki-crl.itn.ftgroup/ca/IGC_Orange-Internal-G2/OIG2%230_root.cer -o OrangeInternalG2RootCA.crt \
    && curl -sSL http://pki-crl.itn.ftgroup/ca/IGC_Orange-Internal-G2/OIG2%231_server.cer -o OrangeInternalG2ServerCA.crt \
    && echo >> OrangeInternalG2RootCA.crt \
    && echo >> OrangeInternalG2ServerCA.crt \
    && cp OrangeInternalG2*.crt /usr/local/share/ca-certificates/ \
    && update-ca-certificates \
    && cat OrangeInternalG2*.crt >> `python3 -m certifi` \
    && python3 -c "import requests; requests.get('https://vault-oab.si.fr.intraorange:8200', verify=True)" \
    # Clean
    && apt-get autoremove -yq \
    && apt-get autoclean -yq \
    && apt-get clean -yq \
    && rm -rf /usr/share/locale/* \
    && rm -rf /var/cache/debconf/* \
    && rm -rf /var/lib/apt-get/lists/* \
    && rm -rf /usr/share/doc/* \
    && rm -rf /tmp/* /var/tmp/*

ENTRYPOINT ["python"]
CMD ["fusion.py"]