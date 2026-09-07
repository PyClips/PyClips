"""Admin coupons and redemption limits. Run from the website folder:

python -m unittest tests.test_admin_coupons
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pyclips-admin-"))
os.environ["PYCLIPS_DATA_DIR"] = str(TMP)
os.environ["PYCLIPS_ADMIN_PASSWORD"] = "test-admin-secret"
os.environ["PYCLIPS_PUBLIC_URL"] = "http://127.0.0.1"

import sys

sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import auth, db
from app.main import app


class AdminCouponTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.get_conn()
        cls.client = TestClient(app)

    def setUp(self):
        conn = db.get_conn()
        conn.execute("DELETE FROM coupon_redemptions")
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM tickets")
        conn.execute("DELETE FROM users")
        conn.commit()
        db.save_coupons({"PYCLIPS-DEV": {"days": 30}})
        db.delete_setting(db.WINDOWS_EXE_KEY)
        from app import billing

        billing._repair_miss_until.clear()
        billing._repairing.clear()

    def _user(self, email: str):
        return auth.create_user(email, "password12", "")

    def test_login_wrong_password(self):
        r = self.client.post("/api/admin/login", json={"password": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_coupons_rejected_without_cookie(self):
        r = self.client.get("/api/admin/coupons")
        self.assertEqual(r.status_code, 401)

    def test_login_create_list_logout(self):
        r = self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.client.cookies.get("pyclips_admin"))
        created = self.client.post("/api/admin/coupons", json={"months": 5, "max_people": 10})
        self.assertEqual(created.status_code, 200, created.text)
        body = created.json()
        self.assertEqual(body["days"], 150)
        self.assertEqual(body["months"], 5)
        self.assertEqual(body["max_redemptions"], 10)
        self.assertTrue(str(body["code"]).startswith("PYCLIPS-"))
        listed = self.client.get("/api/admin/coupons")
        self.assertEqual(listed.status_code, 200)
        codes = [row["code"] for row in listed.json()["coupons"]]
        self.assertIn(body["code"], codes)
        self.assertIn("PYCLIPS-DEV", codes)
        self.client.post("/api/admin/logout")
        again = self.client.get("/api/admin/coupons")
        self.assertEqual(again.status_code, 401)

    def test_create_custom_creator_code(self):
        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        created = self.client.post(
            "/api/admin/coupons",
            json={"months": 1, "max_people": 5, "code": "Sourav15"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["code"], "Sourav15")
        dup = self.client.post(
            "/api/admin/coupons",
            json={"months": 1, "max_people": 5, "code": "sourav15"},
        )
        self.assertEqual(dup.status_code, 400)
        gone = self.client.post("/api/admin/coupons/delete", json={"code": "Sourav15"})
        self.assertEqual(gone.status_code, 200, gone.text)
        listed = self.client.get("/api/admin/coupons")
        row = next(item for item in listed.json()["coupons"] if item["code"] == "Sourav15")
        self.assertTrue(row["archived"])
        self.client.post("/api/admin/logout")

    def test_create_validation(self):
        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        bad = self.client.post("/api/admin/coupons", json={"months": 0, "max_people": 10})
        self.assertEqual(bad.status_code, 422)

    def test_redeem_once_per_user_and_max(self):
        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        created = self.client.post("/api/admin/coupons", json={"months": 1, "max_people": 2})
        code = created.json()["code"]
        self.client.post("/api/admin/logout")

        u1 = self._user("one@example.com")
        u2 = self._user("two@example.com")
        u3 = self._user("three@example.com")
        from app import billing

        billing.redeem_code(u1["id"], code)
        with self.assertRaises(Exception) as dup:
            billing.redeem_code(u1["id"], code)
        self.assertIn("already used", str(dup.exception).lower())
        billing.redeem_code(u2["id"], code)
        with self.assertRaises(Exception) as cap:
            billing.redeem_code(u3["id"], code)
        self.assertIn("reached its limit", str(cap.exception).lower())

    def test_premium_stacks_coupon_days(self):
        from datetime import datetime, timedelta, timezone

        from app import billing

        u1 = self._user("stack@example.com")
        billing.grant_premium(u1["id"], days=10, billing_plan="monthly")
        billing.redeem_code(u1["id"], "PYCLIPS-DEV")
        row = db.get_conn().execute("SELECT premium_until FROM users WHERE id = ?", (u1["id"],)).fetchone()
        until = auth.parse_until(row["premium_until"])
        self.assertIsNotNone(until)
        expect = datetime.now(timezone.utc) + timedelta(days=40)
        self.assertGreater(until, expect - timedelta(days=3))
        self.assertLess(until, expect + timedelta(days=3))

    def test_legacy_pyclips_dev_unlimited_people(self):
        from app import billing

        u1 = self._user("alice@example.com")
        u2 = self._user("bob@example.com")
        billing.redeem_code(u1["id"], "PYCLIPS-DEV")
        billing.redeem_code(u2["id"], "PYCLIPS-DEV")
        with self.assertRaises(Exception):
            billing.redeem_code(u1["id"], "PYCLIPS-DEV")

    def test_desktop_redeem_rejects_email_only(self):
        user = self._user("desk-email@example.com")
        r = self.client.post(
            "/api/desktop/redeem",
            json={"code": "PYCLIPS-DEV", "email": user["email"]},
        )
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("sync_token", r.json())

    def test_desktop_redeem_uses_website_user(self):
        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        created = self.client.post("/api/admin/coupons", json={"months": 2, "max_people": 1})
        code = created.json()["code"]
        user = self._user("desk@example.com")
        from app import tickets

        token = tickets.ensure_desktop_sync_token(user["id"])
        r = self.client.post(
            "/api/desktop/redeem",
            json={"code": code, "email": "desk@example.com", "token": token},
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["plan"], "premium")
        self.assertEqual(data["email"], user["email"])
        self.assertTrue(data.get("sync_token"))

    def test_desktop_license_rejects_email_only(self):
        user = self._user("victim@example.com")
        r = self.client.post("/api/desktop/license", json={"email": user["email"]})
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("sync_token", r.json())

    def test_coupons_survive_missing_json_file(self):
        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        created = self.client.post(
            "/api/admin/coupons",
            json={"months": 3, "max_people": 4, "code": "KeepMe99"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        json_path = db.DATA_DIR / "coupons.json"
        json_path.unlink(missing_ok=True)
        listed = self.client.get("/api/admin/coupons")
        self.assertEqual(listed.status_code, 200, listed.text)
        codes = [row["code"] for row in listed.json()["coupons"]]
        self.assertIn("KeepMe99", codes)
        self.client.post("/api/admin/logout")

    def test_delete_does_not_revoke_redeemed_premium(self):
        from app import billing

        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        created = self.client.post(
            "/api/admin/coupons",
            json={"months": 2, "max_people": 5, "code": "KeepPrem99"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        user = self._user("keep-prem@example.com")
        later = self._user("too-late@example.com")
        billing.redeem_code(user["id"], "KeepPrem99")
        gone = self.client.post("/api/admin/coupons/delete", json={"code": "KeepPrem99"})
        self.assertEqual(gone.status_code, 200, gone.text)
        sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")
        self.assertTrue(sub.get("premium_until"))
        with self.assertRaises(Exception) as cap:
            billing.redeem_code(later["id"], "KeepPrem99")
        self.assertIn("not valid", str(cap.exception).lower())
        self.client.post("/api/admin/logout")

    def test_catalog_wipe_restores_redeemed_codes_and_keeps_premium(self):
        from app import billing

        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        created = self.client.post(
            "/api/admin/coupons",
            json={"months": 3, "max_people": 4, "code": "KeepAfterWipe"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        user = self._user("wipe-keep@example.com")
        billing.redeem_code(user["id"], "KeepAfterWipe")
        conn = db.get_conn()
        conn.execute("DELETE FROM coupons")
        conn.commit()
        json_path = db.DATA_DIR / "coupons.json"
        json_path.unlink(missing_ok=True)
        db._migrate_coupons(conn)
        listed = self.client.get("/api/admin/coupons")
        self.assertEqual(listed.status_code, 200, listed.text)
        codes = [row["code"].upper() for row in listed.json()["coupons"]]
        self.assertIn("KEEPAFTERWIPE", codes)
        sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")
        self.client.post("/api/admin/logout")

    def test_example_seed_does_not_wipe_sqlite_codes(self):
        db.save_coupons({"KeepMeLive": {"days": 90, "months": 3, "max_redemptions": 4}})
        json_path = db.DATA_DIR / "coupons.json"
        json_path.unlink(missing_ok=True)
        db._migrate_coupons(db.get_conn())
        data = db.load_coupons()
        self.assertIn("KeepMeLive", data)
        self.assertEqual(int(data["KeepMeLive"]["days"]), 90)

    def test_paid_premium_returns_after_plan_is_cleared(self):
        from app import billing

        user = self._user("paid-restore@example.com")
        billing.grant_premium(
            user["id"],
            days=30,
            billing_plan="monthly",
            payment_id="pay_RESTORE1",
            amount=1900,
        )
        conn = db.get_conn()
        conn.execute(
            "UPDATE users SET plan = 'free', billing_plan = NULL, premium_until = '2020-01-01T00:00:00Z' WHERE id = ?",
            (user["id"],),
        )
        conn.commit()
        sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")
        self.assertTrue(sub.get("premium_until"))

    def test_redeemed_premium_returns_after_plan_is_cleared(self):
        from app import billing

        user = self._user("redeem-restore@example.com")
        billing.redeem_code(user["id"], "PYCLIPS-DEV")
        conn = db.get_conn()
        conn.execute(
            "UPDATE users SET plan = 'free', billing_plan = NULL, premium_until = '2020-01-01T00:00:00Z' WHERE id = ?",
            (user["id"],),
        )
        conn.commit()
        sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")

    def test_redeemed_premium_returns_after_plan_is_cleared(self):
        from app import billing

        user = self._user("redeem-restore@example.com")
        billing.redeem_code(user["id"], "PYCLIPS-DEV")
        conn = db.get_conn()
        conn.execute(
            "UPDATE users SET plan = 'free', billing_plan = NULL, premium_until = '2020-01-01T00:00:00Z' WHERE id = ?",
            (user["id"],),
        )
        conn.commit()
        sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")

    def test_free_row_with_future_until_is_premium_again(self):
        from datetime import datetime, timedelta, timezone

        from app import billing

        user = self._user("until-kept@example.com")
        billing.grant_premium(user["id"], days=30, billing_plan="monthly")
        conn = db.get_conn()
        conn.execute("UPDATE users SET plan = 'free', billing_plan = NULL WHERE id = ?", (user["id"],))
        conn.commit()
        sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")
        until = auth.parse_until(sub["premium_until"])
        self.assertIsNotNone(until)
        self.assertGreater(until, datetime.now(timezone.utc) + timedelta(days=20))

    def test_expire_does_not_drop_razorpay_subscription_id(self):
        from datetime import datetime, timedelta, timezone

        from app import billing

        user = self._user("keep-sub@example.com")
        billing.grant_premium(user["id"], days=30, billing_plan="monthly", sub_id="sub_KEEPME")
        past = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = db.get_conn()
        conn.execute("UPDATE users SET premium_until = ? WHERE id = ?", (past, user["id"]))
        conn.commit()
        auth.expire_if_needed(user["id"])
        row = conn.execute(
            "SELECT plan, rzp_subscription_id FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
        self.assertEqual(row["plan"], "free")
        self.assertEqual(row["rzp_subscription_id"], "sub_KEEPME")

    def test_payment_captured_webhook_grants_by_email(self):
        import hashlib
        import hmac
        import json

        os.environ["RAZORPAY_WEBHOOK_SECRET"] = "whsec-test"
        user = self._user("hook-pay@example.com")
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_HOOKCAPTURE1",
                        "amount": 1900,
                        "email": "hook-pay@example.com",
                        "notes": {"user_id": str(user["id"]), "plan": "monthly"},
                    }
                }
            },
        }
        raw = json.dumps(payload).encode("utf-8")
        sig = hmac.new(b"whsec-test", raw, hashlib.sha256).hexdigest()
        r = self.client.post("/api/billing/webhook", content=raw, headers={"X-Razorpay-Signature": sig})
        self.assertEqual(r.status_code, 200, r.text)
        sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")

    def test_webhook_stale_user_id_uses_email(self):
        import hashlib
        import hmac
        import json

        os.environ["RAZORPAY_WEBHOOK_SECRET"] = "whsec-test"
        user = self._user("hook-stale@example.com")
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_STALEUSER1",
                        "amount": 1900,
                        "email": "hook-stale@example.com",
                        "notes": {"user_id": "99999", "plan": "monthly"},
                    }
                }
            },
        }
        raw = json.dumps(payload).encode("utf-8")
        sig = hmac.new(b"whsec-test", raw, hashlib.sha256).hexdigest()
        r = self.client.post("/api/billing/webhook", content=raw, headers={"X-Razorpay-Signature": sig})
        self.assertEqual(r.status_code, 200, r.text)
        sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")

    def test_duplicate_payment_id_still_restores_premium(self):
        from app import billing

        user = self._user("dup-pay@example.com")
        billing.grant_premium(
            user["id"],
            days=30,
            billing_plan="monthly",
            payment_id="pay_DUP1",
            amount=1900,
        )
        conn = db.get_conn()
        conn.execute(
            "UPDATE users SET plan = 'free', billing_plan = NULL, premium_until = '2020-01-01T00:00:00Z' WHERE id = ?",
            (user["id"],),
        )
        conn.commit()
        again = billing.grant_premium(
            user["id"],
            days=30,
            billing_plan="monthly",
            payment_id="pay_DUP1",
            amount=1900,
        )
        self.assertEqual(again["plan"], "premium")
        self.assertTrue(again.get("premium_until"))

    def test_captured_razorpay_payment_restores_by_email(self):
        from datetime import datetime, timezone
        from unittest.mock import patch

        from app import billing

        user = self._user("tradingboii14@gmail.com")
        os.environ["RAZORPAY_KEY_ID"] = "rzp_test_repairkeys"
        os.environ["RAZORPAY_KEY_SECRET"] = "test_secret_value"
        created = int(datetime.now(timezone.utc).timestamp()) - 86400
        pay = {
            "id": "pay_TUPAYH3AkQ38El",
            "amount": 1900,
            "status": "captured",
            "email": "tradingboii14@gmail.com",
            "created_at": created,
            "notes": {"plan": "monthly"},
        }

        def fake_get(url, params=None, auth=None, timeout=None):
            class Resp:
                status_code = 200
                content = b"x"
                data = {"items": []}

                def json(self):
                    return self.data

            resp = Resp()
            params = params or {}
            if int(params.get("skip") or 0) > 0:
                return resp
            path = url.rstrip("/")
            if path.endswith("/payments"):
                resp.data = {"items": [pay]}
            elif path.endswith("/subscriptions"):
                resp.data = {"items": []}
            elif path.endswith("/customers"):
                resp.data = {"items": [{"id": "cust_WRONG", "email": "other@example.com"}]}
            else:
                resp.status_code = 404
                resp.content = b""
                resp.data = {}
            return resp

        with patch("app.billing.requests.get", side_effect=fake_get):
            sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")
        row = db.get_conn().execute(
            "SELECT user_id FROM payments WHERE razorpay_payment_id = ?",
            ("pay_TUPAYH3AkQ38El",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(int(row["user_id"]), user["id"])

    def test_orphan_payment_row_is_reclaimed(self):
        from datetime import datetime, timezone
        from unittest.mock import patch

        from app import billing

        user = self._user("orphan-pay@example.com")
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO payments (user_id, razorpay_payment_id, razorpay_subscription_id, amount_paise, kind, created_at) "
            "VALUES (?, ?, '', 1900, 'subscription', ?)",
            (
                99999,
                "pay_ORPHAN1",
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
        conn.commit()
        os.environ["RAZORPAY_KEY_ID"] = "rzp_test_repairkeys"
        os.environ["RAZORPAY_KEY_SECRET"] = "test_secret_value"
        pay = {
            "id": "pay_ORPHAN1",
            "amount": 1900,
            "status": "captured",
            "email": "orphan-pay@example.com",
            "created_at": int(datetime.now(timezone.utc).timestamp()) - 3600,
            "notes": {"plan": "monthly"},
        }

        def fake_get(url, params=None, auth=None, timeout=None):
            class Resp:
                status_code = 200
                content = b"x"
                data = {"items": []}

                def json(self):
                    return self.data

            resp = Resp()
            params = params or {}
            if int(params.get("skip") or 0) > 0:
                return resp
            path = url.rstrip("/")
            if path.endswith("/payments"):
                resp.data = {"items": [pay]}
            elif path.endswith("/subscriptions") or path.endswith("/customers"):
                resp.data = {"items": []}
            else:
                resp.status_code = 404
                resp.content = b""
                resp.data = {}
            return resp

        with patch("app.billing.requests.get", side_effect=fake_get):
            sub = auth.subscription_for(user["id"])
        self.assertEqual(sub["plan"], "premium")
        row = db.get_conn().execute(
            "SELECT user_id FROM payments WHERE razorpay_payment_id = ?",
            ("pay_ORPHAN1",),
        ).fetchone()
        self.assertEqual(int(row["user_id"]), user["id"])

    def test_desktop_refresh_requires_token(self):
        user = self._user("refresh@example.com")
        email_only = self.client.post("/api/desktop/refresh", json={"email": user["email"]})
        self.assertEqual(email_only.status_code, 401)
        self.assertNotIn("sync_token", email_only.json())
        from app import tickets

        token = tickets.ensure_desktop_sync_token(user["id"])
        ok = self.client.post("/api/desktop/refresh", json={"token": token})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["email"], user["email"])

    def test_spa_fallback_and_path_traversal(self):
        from app.config import ROOT, WEB_DIST

        if not (WEB_DIST / "index.html").is_file():
            self.skipTest("website/web/dist/index.html is missing")
        login = self.client.get("/login")
        self.assertEqual(login.status_code, 200)
        self.assertIn("text/html", login.headers.get("content-type", ""))
        privacy = self.client.get("/privacy")
        self.assertEqual(privacy.status_code, 200)
        secret = ROOT / "_traversal_canary.txt"
        secret.write_text("TRAVERSAL_SECRET", encoding="utf-8")
        try:
            for path in ("/../_traversal_canary.txt", "/%2e%2e/_traversal_canary.txt"):
                r = self.client.get(path)
                body = r.content.decode("utf-8", errors="ignore")
                self.assertNotIn("TRAVERSAL_SECRET", body)
                self.assertIn(r.status_code, (200, 404))
                if r.status_code == 200:
                    self.assertIn("<!doctype html>", body.lower())
        finally:
            secret.unlink(missing_ok=True)

    def test_list_includes_storage(self):
        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        listed = self.client.get("/api/admin/coupons")
        self.assertEqual(listed.status_code, 200, listed.text)
        storage = listed.json()["storage"]
        self.assertFalse(storage["ephemeral"])
        self.assertFalse(storage["railway"])
        self.assertTrue(storage["data_dir"])
        self.client.post("/api/admin/logout")

    def test_health_reports_ephemeral_flag(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ephemeral", r.json())
        self.assertFalse(r.json()["ephemeral"])

    def test_unused_code_restored_from_json_mirror(self):
        db.save_coupons({"KeepFromJson": {"days": 60, "months": 2, "max_redemptions": 3}})
        conn = db.get_conn()
        conn.execute("DELETE FROM coupons")
        conn.commit()
        self.assertFalse(db._coupons_from_table(conn))
        self.assertTrue((db.DATA_DIR / "coupons.json").is_file())
        db._migrate_coupons(conn)
        self.assertIn("KeepFromJson", db.load_coupons())

    def test_app_data_is_ephemeral_on_railway(self):
        from app import config

        prev = os.environ.get("RAILWAY_ENVIRONMENT")
        os.environ["RAILWAY_ENVIRONMENT"] = "production"
        try:
            self.assertTrue(config.on_railway())
            self.assertTrue(config.is_ephemeral_data_dir(config.ROOT / "data"))
        finally:
            if prev is None:
                os.environ.pop("RAILWAY_ENVIRONMENT", None)
            else:
                os.environ["RAILWAY_ENVIRONMENT"] = prev


    def test_download_rejected_without_cookie(self):
        self.client.post("/api/admin/logout")
        r = self.client.post(
            "/api/admin/download",
            json={"url": "https://github.com/PyClips/PyClips/releases/download/desktop-1.0.20/PyClips-Setup-1.0.20.exe"},
        )
        self.assertEqual(r.status_code, 401)

    def test_download_rejects_non_github_exe(self):
        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        bad = self.client.post("/api/admin/download", json={"url": "https://example.com/PyClips-Setup.exe"})
        self.assertEqual(bad.status_code, 400, bad.text)
        also = self.client.post(
            "/api/admin/download",
            json={"url": "https://github.com/PyClips/PyClips/blob/main/setup.exe"},
        )
        self.assertEqual(also.status_code, 400, also.text)
        zip_url = self.client.post(
            "/api/admin/download",
            json={"url": "https://github.com/PyClips/PyClips/releases/download/v1/notes.zip"},
        )
        self.assertEqual(zip_url.status_code, 400, zip_url.text)
        self.client.post("/api/admin/logout")

    def test_download_save_redirect_and_clear(self):
        asset = "https://github.com/PyClips/PyClips/releases/download/desktop-1.0.20/PyClips-Setup-1.0.20.exe"
        empty = self.client.get("/api/download")
        self.assertEqual(empty.status_code, 200)
        self.assertFalse(empty.json()["available"])
        missing = self.client.get("/download", follow_redirects=False)
        self.assertEqual(missing.status_code, 404)

        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        saved = self.client.post("/api/admin/download", json={"url": asset})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["url"], asset)
        self.assertEqual(saved.json()["filename"], "PyClips-Setup-1.0.20.exe")
        listed = self.client.get("/api/admin/download")
        self.assertEqual(listed.json()["url"], asset)
        self.client.post("/api/admin/logout")

        public = self.client.get("/api/download")
        self.assertTrue(public.json()["available"])
        self.assertEqual(public.json()["url"], "/download")
        bounced = self.client.get("/download", follow_redirects=False)
        self.assertEqual(bounced.status_code, 302)
        self.assertEqual(bounced.headers.get("location"), asset)

        self.client.post("/api/admin/login", json={"password": "test-admin-secret"})
        cleared = self.client.post("/api/admin/download/clear")
        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.client.post("/api/admin/logout")
        gone = self.client.get("/download", follow_redirects=False)
        self.assertEqual(gone.status_code, 404)
        self.assertFalse(self.client.get("/api/download").json()["available"])


class AdminDisabledTests(unittest.TestCase):
    def test_login_404_without_password(self):
        prev = os.environ.get("PYCLIPS_ADMIN_PASSWORD")
        os.environ["PYCLIPS_ADMIN_PASSWORD"] = ""
        try:
            client = TestClient(app)
            r = client.post("/api/admin/login", json={"password": "x"})
            self.assertEqual(r.status_code, 404)
        finally:
            if prev is None:
                os.environ.pop("PYCLIPS_ADMIN_PASSWORD", None)
            else:
                os.environ["PYCLIPS_ADMIN_PASSWORD"] = prev


if __name__ == "__main__":
    unittest.main()
