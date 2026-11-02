"""Backend tests. Open-Meteo is replaced with a fake fetch function."""

from __future__ import annotations

import os
import unittest
import urllib.error
from unittest import mock

import app as app_module
from weather import CityNotFound, UpstreamError, get_weather, weather_code_to_text

PARIS = {
    "name": "Paris",
    "country": "France",
    "latitude": 48.85341,
    "longitude": 2.3488,
}


def ok_fetch(geo_payload, forecast_payload):
    def fetch(url, timeout):
        if "/v1/search" in url:
            return geo_payload
        if "/v1/forecast" in url:
            return forecast_payload
        raise AssertionError(f"unexpected url {url}")

    return fetch


class WeatherCodeTests(unittest.TestCase):
    def test_known_and_unknown_codes(self):
        self.assertEqual(weather_code_to_text(0), "Clear sky")
        self.assertEqual(weather_code_to_text(3), "Overcast")
        self.assertEqual(weather_code_to_text(95), "Thunderstorm")
        self.assertEqual(weather_code_to_text(123), "Unknown (123)")


class GetWeatherTests(unittest.TestCase):
    def test_returns_current_conditions_for_the_first_match(self):
        seen = []

        def fetch(url, timeout):
            seen.append((url, timeout))
            if "/v1/search" in url:
                return {"results": [PARIS, {"name": "Paris, Texas"}]}
            return {
                "current": {
                    "time": "2026-11-02T21:00",
                    "temperature_2m": 15.5,
                    "weather_code": 2,
                }
            }

        result = get_weather("Paris", fetch=fetch)

        self.assertEqual(result["city"], "Paris")
        self.assertEqual(result["country"], "France")
        self.assertEqual(result["temperature"], 15.5)
        self.assertEqual(result["temperature_unit"], "°C")
        self.assertEqual(result["conditions"], "Partly cloudy")
        self.assertEqual(result["weather_code"], 2)
        self.assertEqual(result["observed_at"], "2026-11-02T21:00")
        self.assertIn("name=Paris", seen[0][0])
        self.assertIn("latitude=48.85341", seen[1][0])
        self.assertIn("longitude=2.3488", seen[1][0])

    def test_base_urls_and_timeout_come_from_the_environment(self):
        with mock.patch.dict(
            os.environ,
            {
                "GEOCODING_API_URL": "http://geo.example/",
                "FORECAST_API_URL": "http://forecast.example/",
                "REQUEST_TIMEOUT_SECONDS": "2.5",
            },
        ):
            seen = []

            def fetch(url, timeout):
                seen.append((url, timeout))
                if "/v1/search" in url:
                    return {"results": [PARIS]}
                return {"current": {"time": "2026-11-02T21:00", "temperature_2m": 1, "weather_code": 0}}

            get_weather("Paris", fetch=fetch)

        self.assertTrue(seen[0][0].startswith("http://geo.example/v1/search?"))
        self.assertTrue(seen[1][0].startswith("http://forecast.example/v1/forecast?"))
        self.assertEqual(seen[0][1], 2.5)

    def test_missing_city_raises(self):
        with self.assertRaises(CityNotFound):
            get_weather("Nowhere", fetch=lambda url, timeout: {"results": []})
        with self.assertRaises(CityNotFound):
            get_weather("Nowhere", fetch=lambda url, timeout: {})

    def test_upstream_failure_raises(self):
        def explode(url, timeout):
            raise urllib.error.URLError("down")

        with self.assertRaises(UpstreamError):
            get_weather("Paris", fetch=explode)

    def test_incomplete_forecast_raises(self):
        fetch = ok_fetch({"results": [PARIS]}, {"current": {"time": "2026-11-02T21:00"}})
        with self.assertRaises(UpstreamError):
            get_weather("Paris", fetch=fetch)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake_get_weather(city):
            self.calls.append(city)
            if city == "missing":
                raise CityNotFound(city)
            if city == "down":
                raise UpstreamError("down")
            return {
                "city": "Paris",
                "country": "France",
                "temperature": 15.5,
                "temperature_unit": "°C",
                "conditions": "Partly cloudy",
            }

        self.client = app_module.create_app(fake_get_weather).test_client()

    def test_health_endpoints(self):
        health = self.client.get("/healthz")
        ready = self.client.get("/readyz")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json(), {"status": "ok"})
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.get_json(), {"status": "ready"})

    def test_missing_city_is_rejected(self):
        response = self.client.get("/api/weather")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "city is required")
        blank = self.client.get("/api/weather?city=%20%20")
        self.assertEqual(blank.status_code, 400)
        self.assertEqual(self.calls, [])

    def test_success_and_error_mapping(self):
        ok = self.client.get("/api/weather?city=Paris")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.get_json()["temperature"], 15.5)
        self.assertEqual(ok.get_json()["conditions"], "Partly cloudy")

        missing = self.client.get("/api/weather?city=missing")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.get_json()["error"], "No results for missing")

        down = self.client.get("/api/weather?city=down")
        self.assertEqual(down.status_code, 502)
        self.assertEqual(down.get_json()["error"], "Weather service is unavailable")
