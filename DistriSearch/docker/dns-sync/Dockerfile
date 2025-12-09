FROM python:3.11-slim

RUN pip install --no-cache-dir docker

WORKDIR /app

COPY sync_dns_zone.py /app/

ENV SYNC_INTERVAL=30 \
    COREDNS_ZONE_PATH=/zones

ENTRYPOINT ["python", "-u", "sync_dns_zone.py"]
