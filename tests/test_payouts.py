"""Creator payouts: every sale recorded, 40 / 30 / 30 split, weekly and monthly payouts."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PYCLIPS_DATA_DIR", str(Path(tempfile.mkdtemp(prefix="pyclips-payouts-"))))
os.environ.setdefault("PYCLIPS_ADMIN_PASSWORD", "test-admin-secret")
os.environ.setdefault("PYCLIPS_PUBLIC_URL", "http://127.0.0.1")
sys.path.insert(0, str(ROOT))

from app import db, payouts  # noqa: E402


def sale(order: str, amount: int, *, sa: str = "", email: str = "buyer@example.com", when: str = "2026-09-22T10:00:00+00:00"):
    url = f"https://checkout.pyclips.in/premium?sa={sa}" if sa else "https://checkout.pyclips.in/premium"
    return {
        "customer": {"email": email, "sourceUrl": url},
        "order": {"id": order, "createdAt": when, "totalPrice": None},
        "pricePlan": {"name": "Monthly" if amount == 99 else "Lifetime", "amount": amount},
    }


class PayoutTests(unittest.TestCase):
    def setUp(self):
        conn = db.get_conn()
        payouts.ensure_tables(conn)
        for table in ("sales", "payouts", "creators"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM site_settings WHERE key = ?", (payouts.PARTNERS_KEY,))
        conn.commit()
        self.lakshya = payouts.save_creator(payouts.CreatorBody(name="Lakshya", affiliate_code="sa001"))["id"]
        self.sourabh = payouts.save_creator(payouts.CreatorBody(name="Sourabh", affiliate_code="sa002"))["id"]

    def record(self, payload, monthly=True):
        email = payload["customer"]["email"]
        return payouts.record_systeme_sale(payload, email=email, order_id=payload["order"]["id"], monthly=monthly)

    def test_split_is_40_30_30_and_always_adds_up(self):
        self.assertEqual(payouts.split(9900), (3960, 2970, 2970))
        self.assertEqual(payouts.split(59900), (23960, 17970, 17970))
        for amount in (1, 7, 9901, 12345):
            self.assertEqual(sum(payouts.split(amount)), amount)

    def test_monthly_and_lifetime_sales_are_both_recorded_and_matched(self):
        self.record(sale("o1", 99, sa="sa001"))
        self.record(sale("o2", 599, sa="SA002", email="b2@example.com"), monthly=False)
        rows = {s["order_id"]: s for s in payouts.list_sales()}
        self.assertEqual(rows["o1"]["amount_paise"], 9900)
        self.assertEqual(rows["o1"]["creator_name"], "Lakshya")
        self.assertEqual(rows["o2"]["amount_paise"], 59900)
        self.assertEqual(rows["o2"]["plan"], "lifetime")
        self.assertEqual(rows["o2"]["creator_name"], "Sourabh")

    def test_webhook_retry_is_not_counted_twice(self):
        self.record(sale("o1", 99, sa="sa001"))
        again = self.record(sale("o1", 99, sa="sa001"))
        self.assertTrue(again["duplicate"])
        self.assertEqual(len(payouts.list_sales()), 1)

    def test_renewal_goes_to_the_same_creator(self):
        self.record(sale("o1", 99, sa="sa001", email="loyal@example.com"))
        renewal = sale("o9", 99, email="loyal@example.com")  # no sa= on the renewal
        self.record(renewal)
        rows = {s["order_id"]: s for s in payouts.list_sales()}
        self.assertEqual(rows["o9"]["creator_name"], "Lakshya")
        self.assertEqual(rows["o9"]["matched_by"], "earlier sale")

    def test_same_order_weeks_later_is_a_renewal(self):
        self.record(sale("o1", 99, sa="sa001", when="2026-08-01T10:00:00+00:00"))
        conn = db.get_conn()
        conn.execute("UPDATE sales SET sold_at = '2026-08-01T10:00:00Z'")
        conn.commit()
        result = self.record(sale("o1", 99, sa="sa001", when="2026-08-01T10:00:00+00:00"))
        self.assertTrue(result["recorded"])
        self.assertEqual(len(payouts.list_sales()), 2)

    def test_unknown_code_lands_in_attention_and_rematches_later(self):
        self.record(sale("o1", 99, sa="sa777", email="new@example.com"))
        summary = payouts.summary()
        self.assertEqual(len(summary["attention"]), 1)
        self.assertIn("sa777", summary["attention"][0]["note"])
        payouts.save_creator(payouts.CreatorBody(name="Forclipping", affiliate_code="sa777"))
        self.assertEqual(payouts.list_sales()[0]["creator_name"], "Forclipping")
        self.assertEqual(payouts.summary()["attention"], [])

    def test_weekly_creator_payout_and_refund_takeback(self):
        # Two sales in the week of Mon 2026-09-21 (IST), one the next week.
        self.record(sale("o1", 99, sa="sa001", email="a@x.com", when="2026-09-21T04:00:00+00:00"))
        self.record(sale("o2", 599, sa="sa001", email="b@x.com", when="2026-09-27T10:00:00+00:00"), monthly=False)
        self.record(sale("o3", 99, sa="sa001", email="c@x.com", when="2026-09-28T10:00:00+00:00"))
        due = {g["week_start"]: g for g in payouts.summary()["creator_due"]}
        self.assertEqual(due["2026-09-21"]["amount_paise"], 3960 + 23960)
        self.assertEqual(due["2026-09-21"]["sales"], 2)
        self.assertEqual(due["2026-09-28"]["amount_paise"], 3960)

        paid = payouts.pay_creator(payouts.CreatorPayBody(creator_id=self.lakshya, week_start="2026-09-21", reference="UTR1"))
        self.assertEqual(paid["amount_paise"], 27920)
        weeks = [g["week_start"] for g in payouts.summary()["creator_due"]]
        self.assertEqual(weeks, ["2026-09-28"])
        with self.assertRaises(Exception):
            payouts.pay_creator(payouts.CreatorPayBody(creator_id=self.lakshya, week_start="2026-09-21"))

        # The ₹599 buyer is refunded after the creator was paid: take it back next time.
        refunded = next(s for s in payouts.list_sales() if s["order_id"] == "o2")
        payouts.update_sale(refunded["id"], payouts.SaleUpdateBody(refunded=True))
        due = {g["week_start"]: g for g in payouts.summary()["creator_due"]}
        self.assertEqual(due["2026-09-21"]["amount_paise"], -23960)
        payouts.pay_creator(payouts.CreatorPayBody(creator_id=self.lakshya, week_start="2026-09-21", reference="deducted"))
        weeks = [g["week_start"] for g in payouts.summary()["creator_due"]]
        self.assertEqual(weeks, ["2026-09-28"])

    def test_monthly_partner_payout(self):
        payouts.set_partner_names(payouts.PartnersBody(first="Sameer", second="Rahul"))
        self.record(sale("o1", 99, sa="sa001", email="a@x.com", when="2026-08-10T10:00:00+00:00"))
        self.record(sale("o2", 599, sa="sa002", email="b@x.com", when="2026-08-20T10:00:00+00:00"), monthly=False)
        month = next(g for g in payouts.summary()["partner_due"] if g["month"] == "2026-08")
        self.assertEqual(month["gross_paise"], 69800)
        self.assertEqual(month["creator_paise"], 3960 + 23960)
        self.assertEqual(month["first_paise"], 2970 + 17970)
        self.assertEqual(month["second_paise"], 2970 + 17970)
        self.assertEqual(month["status"], "due")
        payouts.pay_partners(payouts.PartnerPayBody(month="2026-08", reference="split"))
        self.assertEqual(payouts.summary()["partner_due"], [])
        history = payouts.list_payouts()
        self.assertEqual(history[0]["kind"], "partner")
        self.assertEqual(history[0]["first_paise"], 20940)
        self.assertIn("Rahul", payouts.payouts_csv())

    def test_month_remainder_after_all_creators_is_split_50_50(self):
        extra = payouts.save_creator(payouts.CreatorBody(name="Forclipping", affiliate_code="sa003"))["id"]
        self.assertTrue(extra)
        codes = ["sa001", "sa002", "sa003"]
        for i in range(9):
            self.record(sale(f"m{i}", 99, sa=codes[i % 3], email=f"m{i}@x.com", when="2026-08-12T10:00:00+00:00"))
        self.record(sale("m9", 599, sa="sa002", email="big@x.com", when="2026-08-30T10:00:00+00:00"), monthly=False)
        month = next(g for g in payouts.summary()["partner_due"] if g["month"] == "2026-08")
        gross = 9 * 9900 + 59900
        self.assertEqual(month["gross_paise"], gross)
        left = gross - month["creator_paise"]
        self.assertEqual(month["creator_paise"], 9 * 3960 + 23960)
        self.assertEqual(month["first_paise"] + month["second_paise"], left)
        self.assertLessEqual(abs(month["first_paise"] - month["second_paise"]), 1)

    def test_creator_joins_from_link_and_picks_up_earlier_sales(self):
        self.record(sale("j1", 99, sa="sa0077", email="fan@x.com"))
        self.assertEqual(len(payouts.summary()["attention"]), 1)
        payouts.creator_join(payouts.JoinBody(affiliate_code="sa0077", name="Asha", email="Asha@X.com", pay_to="asha@upi"))
        summary = payouts.summary()
        self.assertEqual(summary["attention"], [])
        self.assertEqual([c["name"] for c in summary["new_creators"]], ["Asha"])
        self.assertEqual(payouts.list_sales()[0]["creator_name"], "Asha")
        with self.assertRaises(Exception):
            payouts.creator_join(payouts.JoinBody(affiliate_code="sa0077", name="Thief", pay_to="thief@upi"))
        asha = next(c for c in payouts.list_creators() if c["name"] == "Asha")
        self.assertEqual(asha["pay_to"], "asha@upi")
        payouts.mark_creator_checked(asha["id"])
        self.assertEqual(payouts.summary()["new_creators"], [])

    def test_join_fills_a_creator_added_by_email_only(self):
        added = payouts.save_creator(payouts.CreatorBody(name="Lead", email="lead@x.com"))
        payouts.creator_join(payouts.JoinBody(affiliate_code="sa0088", name="Lead Real", email="lead@x.com", pay_to="lead@upi"))
        row = next(c for c in payouts.list_creators() if c["id"] == added["id"])
        self.assertEqual((row["affiliate_code"], row["pay_to"], row["name"]), ("sa0088", "lead@upi", "Lead"))

    def test_join_api_is_public(self):
        from fastapi.testclient import TestClient
        from app.main import app

        res = TestClient(app).post("/api/creators/join", json={"affiliate_code": "sa0099", "name": "Pub", "pay_to": "pub@upi"})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(any(c["affiliate_code"] == "sa0099" for c in payouts.list_creators()))

    def test_manual_sale_and_paid_sale_is_locked(self):
        payouts.add_manual_sale(payouts.SaleBody(buyer_email="cash@x.com", plan="monthly", amount_rupees=99,
                                                 creator_id=self.sourabh, sold_on="2026-09-02", order_id="m1"))
        s = payouts.list_sales()[0]
        self.assertEqual(s["creator_paise"], 3960)
        payouts.pay_creator(payouts.CreatorPayBody(creator_id=self.sourabh, week_start=s["week_start"]))
        with self.assertRaises(Exception):
            payouts.update_sale(s["id"], payouts.SaleUpdateBody(amount_rupees=50))
        with self.assertRaises(Exception):
            payouts.update_sale(s["id"], payouts.SaleUpdateBody(creator_id=self.lakshya))

    def test_week_boundaries_use_india_time(self):
        # Sunday 23:00 IST is still the old week; Monday 00:30 IST is the new one.
        sunday = datetime(2026, 9, 27, 17, 30, tzinfo=timezone.utc)
        monday = sunday + timedelta(hours=1, minutes=30)
        self.assertEqual(payouts.week_start(sunday), "2026-09-21")
        self.assertEqual(payouts.week_start(monday), "2026-09-28")


class WebhookTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app import billing, main

        self.client = TestClient(main.app)
        self.billing = billing
        conn = db.get_conn()
        payouts.ensure_tables(conn)
        for table in ("sales", "payouts", "creators", "payments", "users"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()

    def post(self, payload, event="SALE_NEW"):
        import json

        body = json.dumps(payload).encode()
        with patch.object(self.billing, "settings", return_value={"systeme_secret": "s3"}), \
                patch.object(self.billing, "verify_systeme_signature", return_value=True):
            return self.client.post("/api/billing/systeme", content=body,
                                    headers={"X-Webhook-Signature": "x", "X-Webhook-Event": event})

    def test_lifetime_sale_is_recorded_even_without_a_month_grant(self):
        r = self.post(sale("L1", 599, sa="sa001", email="life@x.com"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(payouts.list_sales()[0]["plan"], "lifetime")

    def test_cancel_event_does_not_grant_or_record_a_sale(self):
        self.post(sale("C1", 99, email="c@x.com"))
        r = self.post(sale("C1", 99, email="c@x.com"), event="SALE_CANCELED")
        self.assertEqual(r.json()["canceled"]["updated"], 1)
        sales = payouts.list_sales()
        self.assertEqual(len(sales), 1)
        self.assertTrue(sales[0]["canceled_at"])

    def test_payouts_api_needs_admin(self):
        self.assertEqual(self.client.get("/api/payouts/summary").status_code, 401)
        self.client.post("/api/admin/login", json={"password": os.environ["PYCLIPS_ADMIN_PASSWORD"]})
        r = self.client.get("/api/payouts/summary")
        self.assertEqual(r.status_code, 200)
        self.assertIn("creator_due", r.json())
        csv = self.client.get("/api/payouts/export/sales.csv")
        self.assertEqual(csv.status_code, 200)
        self.assertIn("Creator 40%", csv.text)


if __name__ == "__main__":
    unittest.main()
