"""Frontend tests. The backend HTTP call is replaced with a fake."""

from __future__ import annotations

import json
import os
import unittest
import urllib.error
from io import BytesIO
from unittest import mock

import app as app_module
from app import BackendError, fetch_weather


class FetchWeatherTests(unittest.TestCase):
    def test_calls_backend_url_from_the_environment(self):
        payload = {"city": "Haifa", "temperature": 22, "temperature_unit": "°C", "conditions": "Clear sky"}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(payload).encode()

        with mock.patch.dict(
            os.environ,
            {"BACKEND_URL": "http://backend.internal:8000/", "REQUEST_TIMEOUT_SECONDS": "3"},
        ), mock.patch.object(
            app_module.urllib.request, "urlopen", return_value=Response()
        ) as urlopen:
            result = fetch_weather("Haifa")

        self.assertEqual(result, payload)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://backend.internal:8000/api/weather?city=Haifa")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 3.0)

    def test_http_error_uses_the_backend_message(self):
        error = urllib.error.HTTPError(
            url="http://backend/api/weather",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=BytesIO(b'{"error":"No results for Atlantis"}'),
        )
        with mock.patch.object(
            app_module.urllib.request, "urlopen", side_effect=error
        ), self.assertRaises(BackendError) as raised:
            fetch_weather("Atlantis")
        self.assertEqual(raised.exception.message, "No results for Atlantis")

    def test_connection_error_is_a_stable_message(self):
        with mock.patch.object(
            app_module.urllib.request, "urlopen", side_effect=urllib.error.URLError("down")
        ), self.assertRaises(BackendError) as raised:
            fetch_weather("Haifa")
        self.assertEqual(raised.exception.message, "Weather service is unavailable")


class PageTests(unittest.TestCase):
    def setUp(self):
        def fake_fetch(city):
            if city == "Atlantis":
                raise BackendError("No results for Atlantis")
            if city == "<script>":
                raise BackendError("No results for <script>")
            return {
                "city": city,
                "country": "France",
                "temperature": 15.5,
                "temperature_unit": "°C",
                "conditions": "Partly cloudy",
                "observed_at": "2026-11-02T21:00",
            }

        self.client = app_module.create_app(fake_fetch).test_client()

    def test_metrics_records_the_health_check(self):
        self.client.get("/healthz")
        metrics = self.client.get("/metrics")
        self.assertEqual(metrics.status_code, 200)
        body = metrics.get_data(as_text=True)
        self.assertIn("skywatch_http_requests_total", body)
        self.assertIn('path="/healthz"', body)

    def test_health_endpoints(self):
        self.assertEqual(self.client.get("/healthz").get_json(), {"status": "ok"})
        self.assertEqual(self.client.get("/readyz").get_json(), {"status": "ready"})

    def test_form_renders(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'name="city"', page.data)
        self.assertNotIn(b"Partly cloudy", page.data)

    def test_empty_city_asks_for_a_name(self):
        page = self.client.post("/", data={"city": "   "})
        self.assertIn(b"Enter a city name.", page.data)

    def test_success_shows_temperature_and_conditions(self):
        page = self.client.post("/", data={"city": "Paris"})
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Paris, France", page.data)
        self.assertIn(b"15.5", page.data)
        self.assertIn(b"Partly cloudy", page.data)

    def test_backend_error_is_shown_and_escaped(self):
        page = self.client.post("/", data={"city": "<script>"})
        self.assertIn(b"No results for &lt;script&gt;", page.data)
        self.assertNotIn(b"<script>", page.data)
