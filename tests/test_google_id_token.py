"""Phone Google Sign-In: pyclips.in checks the ID token, then returns a desktop session.

python -m unittest tests.test_google_id_token
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pyclips-gid-"))
os.environ["PYCLIPS_DATA_DIR"] = str(TMP)
os.environ["PYCLIPS_ADMIN_PASSWORD"] = "test-admin-secret"
os.environ["PYCLIPS_PUBLIC_URL"] = "http://127.0.0.1"

import sys

sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import db
from app.main import app

_WEB_CLIENT = "web-client-id.apps.googleusercontent.com"
_TOKEN = "x" * 40


class _GoogleInfo:
    def __init__(self, code: int, payload: dict):
        self.status_code = code
        self._payload = payload

    def json(self):
        return self._payload


def _google_ok(**extra) -> _GoogleInfo:
    payload = {
        "aud": _WEB_CLIENT,
        "iss": "https://accounts.google.com",
        "email_verified": "true",
        "sub": "gid-phone-1",
        "email": "phone.user@gmail.com",
        "name": "Phone",
    }
    payload.update(extra)
    return _GoogleInfo(200, payload)


class GoogleIdTokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.get_conn()
        cls.client = TestClient(app)

    def setUp(self):
        conn = db.get_conn()
        conn.execute("DELETE FROM coupon_redemptions")
        conn.execute("DELETE FROM tickets")
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM users")
        conn.commit()

    def _cfg(self):
        return {
            "google_client_id": _WEB_CLIENT,
            "google_client_secret": "secret",
            "public_url": "http://127.0.0.1",
        }

    def test_missing_token_is_rejected(self):
        r = self.client.post("/api/desktop/google-id-token", json={"id_token": "short"})
        self.assertEqual(r.status_code, 422)

    def test_wrong_audience_is_rejected(self):
        with patch("app.oauth.load_google_config", return_value=self._cfg()):
            with patch("app.oauth.requests.get", return_value=_google_ok(aud="other-app")):
                r = self.client.post("/api/desktop/google-id-token", json={"id_token": _TOKEN})
        self.assertEqual(r.status_code, 401)

    def test_verified_token_returns_sync_token(self):
        with patch("app.oauth.load_google_config", return_value=self._cfg()):
            with patch("app.oauth.requests.get", return_value=_google_ok()):
                r = self.client.post("/api/desktop/google-id-token", json={"id_token": _TOKEN})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["email"], "phone.user@gmail.com")
        self.assertTrue(body["sync_token"])
        self.assertFalse(body["unlimited"])
        self.assertEqual(body["videos_used"], 0)

    def test_same_google_id_reuses_the_account(self):
        with patch("app.oauth.load_google_config", return_value=self._cfg()):
            with patch("app.oauth.requests.get", return_value=_google_ok()):
                first = self.client.post("/api/desktop/google-id-token", json={"id_token": _TOKEN})
                second = self.client.post("/api/desktop/google-id-token", json={"id_token": _TOKEN})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        rows = db.get_conn().execute("SELECT id, google_id FROM users").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["google_id"], "gid-phone-1")
        self.assertEqual(first.json()["sync_token"], second.json()["sync_token"])
