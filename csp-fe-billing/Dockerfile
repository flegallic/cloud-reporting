FROM multirepo-oab.si.fr.intraorange:5002/library/python:3.9.6-slim-buster
LABEL maintainer="Fabrice Le Gallic"

WORKDIR /app
COPY fe.py requirements.txt /app/

RUN pip install -r requirements.txt

ENTRYPOINT ["python"]
CMD ["fe.py"]