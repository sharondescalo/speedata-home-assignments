FROM python:3.12-slim AS build

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

ARG REVISION=dev
LABEL org.opencontainers.image.source="https://github.com/sharondescalo/speedata-home-assignments" \
      org.opencontainers.image.revision="${REVISION}"

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /tmp/prometheus \
    && chown 10001:10001 /tmp/prometheus

WORKDIR /app
COPY --from=build /install /usr/local
COPY app.py metrics.py gunicorn.conf.py ./
COPY templates ./templates

USER app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "30", "-c", "gunicorn.conf.py", "app:app"]
