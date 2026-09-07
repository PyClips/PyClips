"""One Gmail is one website account. Run from the website folder:

python -m unittest tests.test_email_unique
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pyclips-email-"))
os.environ["PYCLIPS_DATA_DIR"] = str(TMP)
os.environ["PYCLIPS_ADMIN_PASSWORD"] = "test-admin-secret"
os.environ["PYCLIPS_PUBLIC_URL"] = "http://127.0.0.1"

import sys

sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app


class EmailUniqueTests(unittest.TestCase):
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

    def test_gmail_aliases_are_the_same_mailbox(self):
        self.assertEqual(
            auth.normalize_email("Microsoft.Testing+tag@Gmail.com"),
            "microsofttesting@gmail.com",
        )
        self.assertEqual(
            auth.normalize_email("microsofttesting@googlemail.com"),
            "microsofttesting@gmail.com",
        )
        self.assertEqual(auth.normalize_email("user.name@yahoo.com"), "user.name@yahoo.com")

    def test_second_register_same_gmail_is_rejected(self):
        first = self.client.post(
            "/api/auth/register",
            json={"email": "microsoft.testing@gmail.com", "password": "password12", "username": "Microsoft"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        again = self.client.post(
            "/api/auth/register",
            json={"email": "microsofttesting@gmail.com", "password": "password12", "username": "Other"},
        )
        self.assertEqual(again.status_code, 409)
        dotted = self.client.post(
            "/api/auth/register",
            json={"email": "m.i.crosoft.testing@gmail.com", "password": "password12"},
        )
        self.assertEqual(dotted.status_code, 409)
        rows = db.get_conn().execute("SELECT email, username FROM users").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "microsoft.testing@gmail.com")

    def test_login_with_dotted_gmail_finds_the_account(self):
        self.client.post(
            "/api/auth/register",
            json={"email": "microsoft.testing@gmail.com", "password": "password12"},
        )
        r = self.client.post(
            "/api/auth/login",
            json={"email": "Microsoft.Testing@gmail.com", "password": "password12"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["user"]["email"], "microsoft.testing@gmail.com")

    def test_login_collapsed_gmail_finds_dotted_account(self):
        self.client.post(
            "/api/auth/register",
            json={"email": "microsoft.testing@gmail.com", "password": "password12"},
        )
        r = self.client.post(
            "/api/auth/login",
            json={"email": "microsofttesting@gmail.com", "password": "password12"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["user"]["email"], "microsoft.testing@gmail.com")

    def test_login_restores_dots_if_account_was_stored_collapsed(self):
        auth.create_user("microsoft.testing@gmail.com", "password12", "Microsoft")
        conn = db.get_conn()
        conn.execute(
            "UPDATE users SET email = ? WHERE email = ?",
            ("microsofttesting@gmail.com", "microsoft.testing@gmail.com"),
        )
        conn.commit()
        r = self.client.post(
            "/api/auth/login",
            json={"email": "sameer.mistry@gmail.com", "password": "nope"},
        )
        self.assertEqual(r.status_code, 401)
        r = self.client.post(
            "/api/auth/login",
            json={"email": "microsoft.testing@gmail.com", "password": "password12"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["user"]["email"], "microsoft.testing@gmail.com")

    def test_google_links_existing_password_account(self):
        created = auth.create_user("microsoft.testing@gmail.com", "password12", "Microsoft")
        linked = auth.upsert_google_user("gid-1", "microsofttesting@gmail.com", "Microsoft Testing")
        self.assertEqual(linked["id"], created["id"])
        n = db.get_conn().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        self.assertEqual(int(n), 1)

    def test_merge_collapses_existing_alias_rows(self):
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO users (email, password_hash, username, plan, created_at) VALUES (?, '', 'One', 'free', '2026-01-01T00:00:00Z')",
            ("microsoft.testing@gmail.com",),
        )
        conn.execute(
            "INSERT INTO users (email, password_hash, username, plan, created_at) VALUES (?, '', 'Two', 'free', '2026-01-02T00:00:00Z')",
            ("microsofttesting@gmail.com",),
        )
        conn.commit()
        auth.merge_duplicate_emails(conn)
        rows = conn.execute("SELECT email, username FROM users").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "microsoft.testing@gmail.com")


if __name__ == "__main__":
    unittest.main()
