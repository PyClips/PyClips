"""Premium must not activate without a captured payment or coupon."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pyclips-billing-"))
os.environ["PYCLIPS_DATA_DIR"] = str(TMP)
os.environ["PYCLIPS_ADMIN_PASSWORD"] = "test-admin-secret"
os.environ["PYCLIPS_PUBLIC_URL"] = "http://127.0.0.1"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_fake"
os.environ["RAZORPAY_KEY_SECRET"] = "fake_secret"

sys.path.insert(0, str(ROOT))

from app import auth, billing, db  # noqa: E402


class PremiumEntitlementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.get_conn()

    def setUp(self):
        conn = db.get_conn()
        conn.execute("DELETE FROM coupon_redemptions")
        conn.execute("DELETE FROM payments")
        conn.execute("DELETE FROM users")
        conn.commit()

    def _insert_user(self, email: str = "new@gmail.com") -> int:
        conn = db.get_conn()
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, username, plan, created_at) VALUES (?, '', ?, 'free', ?)",
            (email, "testuser", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        conn.commit()
        return int(cur.lastrowid)

    def test_unpaid_subscription_does_not_grant_premium(self):
        uid = self._insert_user()
        cfg = {"plan_monthly": "plan_m", "plan_yearly": "plan_y", "plan_monthly_usd": "", "plan_yearly_usd": ""}
        future = int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp())
        entity = {
            "id": "sub_unpaid",
            "status": "created",
            "paid_count": 0,
            "current_end": future,
            "plan_id": "plan_y",
            "notes": {"user_id": str(uid), "plan": "yearly"},
        }
        self.assertFalse(billing._apply_rzp_subscription(uid, cfg, entity))
        row = db.get_conn().execute("SELECT plan, premium_until FROM users WHERE id = ?", (uid,)).fetchone()
        self.assertEqual(row["plan"], "free")
        self.assertIsNone(row["premium_until"])

    def test_paid_subscription_grants_premium(self):
        uid = self._insert_user()
        cfg = {"plan_monthly": "plan_m", "plan_yearly": "plan_y", "plan_monthly_usd": "", "plan_yearly_usd": ""}
        future = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        entity = {
            "id": "sub_paid",
            "status": "active",
            "paid_count": 1,
            "current_end": future,
            "plan_id": "plan_m",
            "notes": {"user_id": str(uid), "plan": "monthly"},
        }
        self.assertTrue(billing._apply_rzp_subscription(uid, cfg, entity))
        row = db.get_conn().execute("SELECT plan, premium_until FROM users WHERE id = ?", (uid,)).fetchone()
        self.assertEqual(row["plan"], "premium")
        self.assertIsNotNone(row["premium_until"])

    def test_revoke_false_premium_on_repair(self):
        uid = self._insert_user()
        until = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = db.get_conn()
        conn.execute(
            "UPDATE users SET plan = 'premium', billing_plan = 'yearly', premium_until = ? WHERE id = ?",
            (until, uid),
        )
        conn.commit()
        with patch.object(billing, "_restore_from_razorpay", return_value=False):
            with patch.object(billing, "_restore_from_local", return_value=False):
                billing.repair_premium(uid)
        row = conn.execute("SELECT plan, premium_until FROM users WHERE id = ?", (uid,)).fetchone()
        self.assertEqual(row["plan"], "free")
        self.assertIsNone(row["premium_until"])


if __name__ == "__main__":
    unittest.main()
