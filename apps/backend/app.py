"""SkyWatch backend. Looks up current weather for a city."""

from __future__ import annotations

import os

from flask import Flask, request
from metrics import install_metrics
from weather import CityNotFound, UpstreamError, get_weather


def create_app(get_weather_fn=get_weather) -> Flask:
    app = Flask(__name__)
    install_metrics(app)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        return {"status": "ready"}

    @app.get("/api/weather")
    def weather():
        city = request.args.get("city", "").strip()
        if not city:
            return {"error": "city is required"}, 400
        try:
            return get_weather_fn(city)
        except CityNotFound:
            return {"error": f"No results for {city}"}, 404
        except UpstreamError:
            return {"error": "Weather service is unavailable"}, 502

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
