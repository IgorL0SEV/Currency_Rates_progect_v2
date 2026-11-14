"""Тесты модульной версии без сети: requests и файлы подменяются."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest import mock

import requests

import api_client
import cli
import currency
import storage


def make_payload(base: str = "USD") -> dict:
    return {
        "result": "success",
        "base_code": base,
        "time_last_update_utc": "Sat, 14 Nov 2026 00:02:31 +0000",
        "time_next_update_utc": "Sun, 15 Nov 2026 00:29:01 +0000",
        "rates": {"USD": 1.0, "RUB": 82.5, "EUR": 0.9, "GBP": 0.75},
    }


class FakeResponse:
    def __init__(self, status_code=200, payload=None, reason="OK"):
        self.status_code = status_code
        self.reason = reason
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class ApiClientTest(unittest.TestCase):
    def test_returns_payload_dict(self):
        payload = make_payload()
        with mock.patch.object(api_client.requests, "get", return_value=FakeResponse(payload=payload)) as get:
            result = api_client.get_currency_rates("usd")
        self.assertEqual(result, payload)
        self.assertEqual(get.call_args.args[0], "https://open.er-api.com/v6/latest/USD")

    def test_http_error_is_readable(self):
        with mock.patch.object(api_client.requests, "get", return_value=FakeResponse(500, reason="Server Error")):
            with self.assertRaises(api_client.CurrencyError) as ctx:
                api_client.get_currency_rates("USD")
        self.assertIn("HTTP 500", str(ctx.exception))

    def test_network_error_is_readable(self):
        with mock.patch.object(api_client.requests, "get", side_effect=requests.ConnectionError("no network")):
            with self.assertRaises(api_client.CurrencyError) as ctx:
                api_client.get_currency_rates("USD")
        self.assertIn("Не удалось связаться", str(ctx.exception))

    def test_api_error_with_http_200(self):
        payload = {"result": "error", "error-type": "unsupported-code"}
        with mock.patch.object(api_client.requests, "get", return_value=FakeResponse(payload=payload)):
            with self.assertRaises(api_client.CurrencyError) as ctx:
                api_client.get_currency_rates("XXX")
        self.assertIn("unsupported-code", str(ctx.exception))

    def test_not_json(self):
        with mock.patch.object(api_client.requests, "get", return_value=FakeResponse(payload=None)):
            with self.assertRaises(api_client.CurrencyError) as ctx:
                api_client.get_currency_rates("USD")
        self.assertIn("не является JSON", str(ctx.exception))

    def test_empty_base(self):
        with self.assertRaises(api_client.CurrencyError):
            api_client.get_currency_rates("  ")

    def test_invalid_code_format_is_rejected_locally(self):
        with mock.patch.object(api_client.requests, "get", side_effect=AssertionError("network called")):
            for bad in ("1", "US", "US D", "€"):
                with self.assertRaises(api_client.CurrencyError) as ctx:
                    api_client.get_currency_rates(bad)
                self.assertIn("три латинские буквы", str(ctx.exception))

    def test_conversion_rates_fallback(self):
        payload = {
            "result": "success",
            "base_code": "USD",
            "conversion_rates": {"USD": 1.0, "RUB": 80.0},
        }
        self.assertEqual(api_client.extract_rates(payload)["RUB"], 80.0)


class StorageTest(unittest.TestCase):
    def test_save_and_read_keeps_cyrillic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            data = {"base_code": "USD", "note": "Рубль", "rates": {"RUB": 82.5}}
            storage.save_to_file(data, path)
            with open(path, encoding="utf-8") as file:
                raw = file.read()
            self.assertIn("Рубль", raw)
            self.assertIn("\n    ", raw)  # indent=4
            self.assertEqual(storage.read_from_file(path), data)

    def test_cache_freshness(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            self.assertFalse(storage.is_cache_fresh(path))
            storage.save_to_file(make_payload(), path)
            self.assertTrue(storage.is_cache_fresh(path))
            old = time.time() - 25 * 60 * 60
            os.utime(path, (old, old))
            self.assertFalse(storage.is_cache_fresh(path))


class ServiceTest(unittest.TestCase):
    def test_fresh_cache_does_not_call_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload(), path)
            with mock.patch.object(api_client.requests, "get", side_effect=AssertionError("network called")):
                payload, source = currency.load_rates("USD", path)
        self.assertEqual(source, "кэш")
        self.assertEqual(payload["base_code"], "USD")

    def test_stale_cache_calls_api_and_updates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload("USD"), path)
            old = time.time() - 25 * 60 * 60
            os.utime(path, (old, old))
            fresh = make_payload("USD")
            fresh["time_last_update_utc"] = "fresh"
            with mock.patch.object(api_client.requests, "get", return_value=FakeResponse(payload=fresh)) as get:
                payload, source = currency.load_rates("USD", path)
            self.assertEqual(source, "API")
            self.assertEqual(get.call_count, 1)
            self.assertEqual(storage.read_from_file(path)["time_last_update_utc"], "fresh")

    def test_cache_for_another_base_is_refetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload("USD"), path)
            eur = make_payload("EUR")
            with mock.patch.object(api_client.requests, "get", return_value=FakeResponse(payload=eur)) as get:
                payload, source = currency.load_rates("EUR", path)
            self.assertEqual(source, "API")
            self.assertEqual(payload["base_code"], "EUR")
            self.assertEqual(get.call_count, 1)

    def test_convert_usd_to_rub(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload("USD"), path)
            result, source = currency.convert(100, "USD", "RUB", path)
        self.assertAlmostEqual(result, 8250.0)
        self.assertEqual(source, "кэш")

    def test_convert_eur_to_gbp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload("EUR"), path)
            result, _ = currency.convert(10, "EUR", "GBP", path)
        self.assertAlmostEqual(result, 10 * 0.75 / 0.9)

    def test_convert_unknown_currency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload("USD"), path)
            with self.assertRaises(currency.CurrencyError) as ctx:
                currency.convert(10, "USD", "ZZZ", path)
        self.assertIn("ZZZ", str(ctx.exception))

    def test_force_refresh_ignores_fresh_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload("USD"), path)
            fresh = make_payload("USD")
            fresh["time_last_update_utc"] = "forced"
            with mock.patch.object(api_client.requests, "get", return_value=FakeResponse(payload=fresh)) as get:
                payload, source = currency.load_rates("USD", path, force_refresh=True)
            self.assertEqual(source, "API")
            self.assertEqual(get.call_count, 1)
            self.assertEqual(storage.read_from_file(path)["time_last_update_utc"], "forced")

    def test_convert_invalid_target_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload("USD"), path)
            with self.assertRaises(currency.CurrencyError) as ctx:
                currency.convert(10, "USD", "1", path)
        self.assertIn("три латинские буквы", str(ctx.exception))

    def test_cached_and_fresh_give_same_conversion(self):
        fresh = make_payload("USD")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            with mock.patch.object(api_client.requests, "get", return_value=FakeResponse(payload=fresh)):
                from_api, _ = currency.convert(100, "USD", "RUB", path)
            cached, _ = currency.convert(100, "USD", "RUB", path)
        self.assertAlmostEqual(from_api, cached, places=10)


class CliTest(unittest.TestCase):
    def test_available_codes_use_fresh_cache_for_any_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "rates.json")
            storage.save_to_file(make_payload("EUR"), path)
            with mock.patch.object(api_client.requests, "get", side_effect=AssertionError("network called")):
                codes, source = cli._available_codes(path)
        self.assertEqual(source, "кэш")
        self.assertEqual(codes, ["EUR", "GBP", "RUB", "USD"])


class FacadeTest(unittest.TestCase):
    def test_required_functions_are_available_from_currency(self):
        self.assertIs(currency.get_currency_rates, api_client.get_currency_rates)
        self.assertIs(currency.save_to_file, storage.save_to_file)
        self.assertIs(currency.read_from_file, storage.read_from_file)


if __name__ == "__main__":
    unittest.main()
