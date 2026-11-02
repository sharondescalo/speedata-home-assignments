"""SkyWatch frontend. A city form that renders the backend weather result."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, render_template, request

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 5.0


class BackendError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def settings() -> dict[str, str | float]:
    timeout_raw = os.environ.get("REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise BackendError("REQUEST_TIMEOUT_SECONDS must be a number") from exc
    if timeout <= 0:
        raise BackendError("REQUEST_TIMEOUT_SECONDS must be positive")
    return {
        "backend_url": os.environ.get("BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/"),
        "timeout": timeout,
    }


def fetch_weather(city: str) -> dict:
    """Call the backend weather API and return the JSON object."""
    config = settings()
    query = urllib.parse.urlencode({"city": city})
    url = f"{config['backend_url']}/api/weather?{query}"
    http_request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "skywatch-frontend/0.1"},
    )
    try:
        with urllib.request.urlopen(http_request, timeout=float(config["timeout"])) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = _error_payload(exc)
        message = payload.get("error") or "Weather service is unavailable"
        raise BackendError(str(message)) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BackendError("Weather service is unavailable") from exc
    if not isinstance(payload, dict):
        raise BackendError("Weather service is unavailable")
    return payload


def _error_payload(exc: urllib.error.HTTPError) -> dict:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def create_app(fetch_weather_fn=fetch_weather) -> Flask:
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        return {"status": "ready"}

    @app.route("/", methods=["GET", "POST"])
    def index():
        city = ""
        weather = None
        error = None
        if request.method == "POST":
            city = request.form.get("city", "").strip()
            if not city:
                error = "Enter a city name."
            else:
                try:
                    weather = fetch_weather_fn(city)
                except BackendError as exc:
                    error = exc.message
        return render_template("index.html", city=city, weather=weather, error=error)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
