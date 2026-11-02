"""Open-Meteo client for SkyWatch.

Geocode a city name, then fetch the current temperature and conditions.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_GEOCODING_API_URL = "https://geocoding-api.open-meteo.com"
DEFAULT_FORECAST_API_URL = "https://api.open-meteo.com"
DEFAULT_TIMEOUT_SECONDS = 5.0

# WMO weather interpretation codes used by Open-Meteo.
# https://open-meteo.com/en/docs
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class CityNotFound(Exception):
    """Geocoding returned no match for the requested city."""


class UpstreamError(Exception):
    """Open-Meteo could not be reached or returned an unusable payload."""


def settings() -> dict[str, str | float]:
    """Read backend configuration. Environment overrides the defaults."""
    timeout_raw = os.environ.get("REQUEST_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise UpstreamError("REQUEST_TIMEOUT_SECONDS must be a number") from exc
    if timeout <= 0:
        raise UpstreamError("REQUEST_TIMEOUT_SECONDS must be positive")
    return {
        "geocoding_api_url": os.environ.get("GEOCODING_API_URL", DEFAULT_GEOCODING_API_URL).rstrip("/"),
        "forecast_api_url": os.environ.get("FORECAST_API_URL", DEFAULT_FORECAST_API_URL).rstrip("/"),
        "timeout": timeout,
    }


def weather_code_to_text(code: int) -> str:
    return WEATHER_CODES.get(code, f"Unknown ({code})")


def fetch_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "skywatch-backend/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise UpstreamError("Open-Meteo request failed") from exc
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise UpstreamError("Open-Meteo returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise UpstreamError("Open-Meteo returned an unexpected payload")
    return payload


def get_weather(city: str, fetch=fetch_json) -> dict:
    """Resolve a city to coordinates, then return the current conditions."""
    config = settings()
    timeout = float(config["timeout"])
    place = _geocode(city, str(config["geocoding_api_url"]), timeout, fetch)
    current = _forecast(
        place["latitude"],
        place["longitude"],
        str(config["forecast_api_url"]),
        timeout,
        fetch,
    )
    code = _require_int(current, "weather_code")
    return {
        "city": place["name"],
        "country": place.get("country"),
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "temperature": _require_number(current, "temperature_2m"),
        "temperature_unit": "°C",
        "conditions": weather_code_to_text(code),
        "weather_code": code,
        "observed_at": _require_str(current, "time"),
    }


def _geocode(city: str, base_url: str, timeout: float, fetch) -> dict:
    url = _url(
        base_url,
        "/v1/search",
        {"name": city, "count": 1, "language": "en", "format": "json"},
    )
    payload = _call_fetch(fetch, url, timeout)
    results = payload.get("results") or []
    if not results:
        raise CityNotFound(city)
    place = results[0]
    if not isinstance(place, dict):
        raise UpstreamError("Open-Meteo geocoding result was unusable")
    return {
        "name": _require_str(place, "name"),
        "country": place.get("country"),
        "latitude": _require_number(place, "latitude"),
        "longitude": _require_number(place, "longitude"),
    }


def _forecast(latitude: float, longitude: float, base_url: str, timeout: float, fetch) -> dict:
    url = _url(
        base_url,
        "/v1/forecast",
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,weather_code",
            "timezone": "auto",
        },
    )
    payload = _call_fetch(fetch, url, timeout)
    current = payload.get("current")
    if not isinstance(current, dict):
        raise UpstreamError("Open-Meteo forecast did not include current conditions")
    return current


def _call_fetch(fetch, url: str, timeout: float) -> dict:
    try:
        payload = fetch(url, timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpstreamError("Open-Meteo request failed") from exc
    if not isinstance(payload, dict):
        raise UpstreamError("Open-Meteo returned an unexpected payload")
    return payload


def _url(base_url: str, path: str, params: dict) -> str:
    return f"{base_url}{path}?{urllib.parse.urlencode(params)}"


def _require_number(payload: dict, key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UpstreamError(f"Open-Meteo response missing {key}")
    return float(value)


def _require_int(payload: dict, key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise UpstreamError(f"Open-Meteo response missing {key}")
    return value


def _require_str(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise UpstreamError(f"Open-Meteo response missing {key}")
    return value
