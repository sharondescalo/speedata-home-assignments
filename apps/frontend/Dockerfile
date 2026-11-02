FROM python:3.12-slim AS build

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

ARG REVISION=dev
LABEL org.opencontainers.image.source="https://github.com/sharondescalo/speedata-home-assignments" \
      org.opencontainers.image.revision="${REVISION}"

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=build /install /usr/local
COPY app.py .
COPY templates ./templates

USER app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "30", "app:app"]
