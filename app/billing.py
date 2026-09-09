"""Razorpay Subscriptions — INR (India) + International USD (outside India)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from requests.auth import HTTPBasicAuth

from . import auth, db
from .config import (
    CURRENCY,
    CURRENCY_USD,
    MONTHLY_CENTS,
    MONTHLY_DAYS,
    MONTHLY_PAISE,
    MONTHLY_PAISE_MIN,
    YEARLY_CENTS,
    YEARLY_DAYS,
    YEARLY_PAISE,
    razorpay_intl_ready,
    razorpay_ready,
    settings,
)

logger = logging.getLogger(__name__)

_TIMEOUT = 20
_RZP = "https://api.razorpay.com/v1"


class SubscribeBody(BaseModel):
    plan: str = Field(default="monthly")
    ticket: str = Field(default="", max_length=64)
    currency: str = Field(default="", max_length=8)


class VerifySubBody(BaseModel):
    razorpay_payment_id: str = Field(min_length=8, max_length=64)
    razorpay_subscription_id: str = Field(min_length=8, max_length=64)
    razorpay_signature: str = Field(min_length=8, max_length=128)
    ticket: str = Field(default="", max_length=64)


class RedeemBody(BaseModel):
    code: str = Field(min_length=3, max_length=64)


def find_coupon(coupons: dict, code: str):
    raw = (code or "").strip()
    if not raw or not isinstance(coupons, dict):
        return None, None
    if raw in coupons:
        return raw, coupons[raw]
    upper = raw.upper()
    if upper in coupons:
        return upper, coupons[upper]
    for key, spec in coupons.items():
        if str(key).upper() == upper:
            return str(key), spec
    return None, None


def coupon_days(spec) -> int:
    if isinstance(spec, (int, float)):
        return max(1, int(spec))
    if not isinstance(spec, dict):
        return 30
    if spec.get("days") not in (None, ""):
        try:
            return max(1, int(spec["days"]))
        except (TypeError, ValueError):
            pass
    if spec.get("months") not in (None, ""):
        try:
            return max(1, int(spec["months"]) * 30)
        except (TypeError, ValueError):
            pass
    return 30


def coupon_max_redemptions(spec) -> int | None:
    if not isinstance(spec, dict):
        return None
    if "max_redemptions" not in spec or spec.get("max_redemptions") in (None, ""):
        return None
    try:
        n = int(spec["max_redemptions"])
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def coupon_archived(spec) -> bool:
    return isinstance(spec, dict) and bool(spec.get("archived"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _auth_pair(cfg: dict) -> HTTPBasicAuth:
    return HTTPBasicAuth(cfg["key_id"], cfg["key_secret"])


def _plan_meta(kind: str, currency: str = "INR") -> tuple[str, int, int, str]:
    """Return (plan_id, amount_minor, days, currency)."""
    cfg = settings()
    kind = (kind or "monthly").strip().lower()
    currency = (currency or CURRENCY).strip().upper()
    if currency not in (CURRENCY, CURRENCY_USD):
        currency = CURRENCY
    if currency == CURRENCY_USD:
        if not razorpay_intl_ready(cfg):
            raise HTTPException(
                status_code=503,
                detail="International (USD) plans are not configured. Add RAZORPAY_PLAN_MONTHLY_USD and RAZORPAY_PLAN_YEARLY_USD.",
            )
        if kind == "yearly":
            pid = cfg["plan_yearly_usd"]
            return pid, YEARLY_CENTS, YEARLY_DAYS, CURRENCY_USD
        pid = cfg["plan_monthly_usd"]
        return pid, MONTHLY_CENTS, MONTHLY_DAYS, CURRENCY_USD
    if not razorpay_ready(cfg):
        raise HTTPException(status_code=503, detail="Razorpay INR plans are not configured on the server.")
    if kind == "yearly":
        pid = cfg["plan_yearly"]
        if not pid:
            raise HTTPException(status_code=503, detail="Yearly plan is not configured on the server.")
        return pid, YEARLY_PAISE, YEARLY_DAYS, CURRENCY
    pid = cfg["plan_monthly"]
    if not pid:
        raise HTTPException(status_code=503, detail="Monthly plan is not configured on the server.")
    return pid, MONTHLY_PAISE, MONTHLY_DAYS, CURRENCY


def _keys_ready(cfg: dict | None = None) -> bool:
    cfg = cfg if cfg is not None else settings()
    kid = str(cfg.get("key_id") or "")
    sec = str(cfg.get("key_secret") or "")
    return bool(kid.startswith("rzp_") and sec and "xxxx" not in kid.lower())


def _notes(entity) -> dict:
    raw = entity.get("notes") if isinstance(entity, dict) else None
    return raw if isinstance(raw, dict) else {}


def _same_mailbox(left: str, right: str) -> bool:
    a, b = auth.canonical_email(left), auth.canonical_email(right)
    return bool(a) and a == b


def _entity_mailbox(entity: dict) -> str:
    notes = _notes(entity)
    return str(
        entity.get("email")
        or entity.get("customer_email")
        or notes.get("email")
        or ""
    )


def _entity_user_id(entity: dict) -> int:
    try:
        return int(_notes(entity).get("user_id") or 0)
    except (TypeError, ValueError):
        return 0


def _user_exists(user_id: int) -> bool:
    row = db.get_conn().execute("SELECT id FROM users WHERE id = ?", (int(user_id),)).fetchone()
    return bool(row)


def _belongs_to_user(entity: dict, user_id: int, email: str, cust_id: str = "") -> bool:
    if not isinstance(entity, dict):
        return False
    noted = _entity_user_id(entity)
    if noted and noted == int(user_id):
        return True
    if cust_id and str(entity.get("customer_id") or "") == cust_id:
        return True
    if email and _same_mailbox(_entity_mailbox(entity), email):
        return True
    return False


def _claim_payment_id(user_id: int, payment_id: str, email: str = "") -> bool:
    """Keep this payment on this account. Reassign if the old owner row is gone or is the same mailbox."""
    payment_id = (payment_id or "").strip()
    if not payment_id:
        return True
    conn = db.get_conn()
    prior = conn.execute(
        "SELECT user_id FROM payments WHERE razorpay_payment_id = ?",
        (payment_id,),
    ).fetchone()
    if not prior:
        return True
    owner = int(prior["user_id"])
    if owner == int(user_id):
        return True
    other = conn.execute("SELECT id, email FROM users WHERE id = ?", (owner,)).fetchone()
    if other is None or (email and _same_mailbox(other["email"], email)):
        conn.execute(
            "UPDATE payments SET user_id = ? WHERE razorpay_payment_id = ?",
            (user_id, payment_id),
        )
        conn.commit()
        return True
    return False


def grant_premium(
    user_id: int,
    *,
    days: int,
    billing_plan: str,
    payment_id: str = "",
    sub_id: str = "",
    amount: int = 0,
    provider: str = "razorpay",
    currency: str = "INR",
) -> dict:
    provider = "razorpay"
    currency = (currency or CURRENCY).strip().upper()
    if currency not in (CURRENCY, CURRENCY_USD):
        currency = CURRENCY
    conn = db.get_conn()
    owner = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if not owner:
        return {"plan": "free", "premium_until": None}
    email = str(owner["email"] or "")
    if payment_id and not _claim_payment_id(user_id, payment_id, email):
        from . import tickets

        tickets.mark_paid_for_user(user_id)
        return auth.subscription_for(user_id)
    if payment_id:
        prior = conn.execute(
            "SELECT created_at, amount_paise, kind FROM payments WHERE razorpay_payment_id = ? AND user_id = ?",
            (payment_id, user_id),
        ).fetchone()
        if prior:
            paid_days, paid_kind = _days_for_amount(
                int(prior["amount_paise"] or amount or 0),
                str(prior["kind"] or billing_plan or ""),
                currency=currency,
            )
            start = auth.parse_until(prior["created_at"]) or _now()
            ensure_premium_until(
                user_id,
                start + timedelta(days=paid_days),
                billing_plan=paid_kind or billing_plan,
                sub_id=sub_id,
            )
            from . import tickets

            tickets.mark_paid_for_user(user_id)
            return auth.subscription_for(user_id)
    row = conn.execute("SELECT premium_until FROM users WHERE id = ?", (user_id,)).fetchone()
    start = _now()
    current = auth.parse_until(row["premium_until"] if row else None)
    if current and current > start:
        start = current
    until = start + timedelta(days=max(1, int(days)))
    stamp = until.strftime("%Y-%m-%dT%H:%M:%SZ")
    changed = conn.execute(
        """UPDATE users SET plan = 'premium', premium_until = ?, billing_plan = ?,
           rzp_subscription_id = COALESCE(NULLIF(?, ''), rzp_subscription_id) WHERE id = ?""",
        (stamp, billing_plan, sub_id or "", user_id),
    )
    if changed.rowcount == 0:
        conn.rollback()
        return {"plan": "free", "premium_until": None}
    if payment_id:
        try:
            conn.execute(
                "INSERT INTO payments (user_id, razorpay_payment_id, razorpay_subscription_id, amount_paise, kind, provider, created_at) "
                "VALUES (?, ?, ?, ?, 'subscription', ?, ?)",
                (user_id, payment_id, sub_id or "", amount, provider, _now().strftime("%Y-%m-%dT%H:%M:%SZ")),
            )
        except sqlite3.IntegrityError:
            _claim_payment_id(user_id, payment_id, email)
    conn.commit()
    from . import tickets

    tickets.mark_paid_for_user(user_id)
    return auth.subscription_for(user_id)


_repairing: set[int] = set()
_repair_miss_until: dict[int, datetime] = {}


def _days_for_amount(amount: int, kind: str = "", *, currency: str = "INR") -> tuple[int, str]:
    kind = (kind or "").strip().lower()
    currency = (currency or CURRENCY).strip().upper()
    if kind == "yearly":
        return YEARLY_DAYS, "yearly"
    if kind == "coupon":
        return MONTHLY_DAYS, "coupon"
    if kind == "monthly":
        return MONTHLY_DAYS, "monthly"
    if currency == CURRENCY_USD:
        if int(amount or 0) >= YEARLY_CENTS:
            return YEARLY_DAYS, "yearly"
        return MONTHLY_DAYS, "monthly"
    if int(amount or 0) >= YEARLY_PAISE:
        return YEARLY_DAYS, "yearly"
    return MONTHLY_DAYS, "monthly"


def ensure_premium_until(
    user_id: int,
    until: datetime,
    *,
    billing_plan: str,
    sub_id: str = "",
    provider: str = "razorpay",
) -> bool:
    """Set Premium to this end date if it is still in the future. Never shortens a later date."""
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    until = until.astimezone(timezone.utc)
    now = _now()
    if until <= now:
        return False
    conn = db.get_conn()
    row = conn.execute(
        "SELECT plan, premium_until FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    current = auth.parse_until(row["premium_until"] if row else None)
    if current and current >= until:
        conn.execute(
            "UPDATE users SET plan = 'premium' WHERE id = ? AND plan != 'premium'",
            (user_id,),
        )
        if sub_id:
            conn.execute(
                "UPDATE users SET rzp_subscription_id = COALESCE(NULLIF(?, ''), rzp_subscription_id) WHERE id = ?",
                (sub_id, user_id),
            )
        conn.commit()
        return True
    stamp = until.strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        """UPDATE users SET plan = 'premium', premium_until = ?, billing_plan = ?,
           rzp_subscription_id = COALESCE(NULLIF(?, ''), rzp_subscription_id) WHERE id = ?""",
        (stamp, billing_plan, sub_id or "", user_id),
    )
    conn.commit()
    return True


def _restore_from_local(user_id: int) -> bool:
    conn = db.get_conn()
    best: datetime | None = None
    plan = "monthly"
    sub_id = ""
    for pay in conn.execute(
        "SELECT amount_paise, kind, created_at, razorpay_subscription_id FROM payments WHERE user_id = ?",
        (user_id,),
    ):
        start = auth.parse_until(pay["created_at"])
        if not start:
            continue
        days, kind = _days_for_amount(int(pay["amount_paise"] or 0), str(pay["kind"] or ""))
        cand = start + timedelta(days=days)
        if best is None or cand > best:
            best, plan = cand, kind
            sub_id = str(pay["razorpay_subscription_id"] or "")
    coupons = db.load_coupons()
    for red in conn.execute(
        "SELECT code, created_at, days FROM coupon_redemptions WHERE user_id = ?",
        (user_id,),
    ):
        start = auth.parse_until(red["created_at"])
        if not start:
            continue
        stored_days = red["days"]
        if stored_days not in (None, ""):
            try:
                days = max(1, int(stored_days))
            except (TypeError, ValueError):
                days = 0
        else:
            days = 0
        if not days:
            _stored, spec = find_coupon(coupons, str(red["code"] or ""))
            days = coupon_days(spec) if spec is not None else MONTHLY_DAYS
        cand = start + timedelta(days=days)
        if best is None or cand > best:
            best, plan, sub_id = cand, "coupon", ""
    if best is None:
        return False
    return ensure_premium_until(user_id, best, billing_plan=plan, sub_id=sub_id)


def _unix_to_dt(value) -> datetime | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return datetime.fromtimestamp(n, tz=timezone.utc)


def _plan_days(kind: str) -> int:
    return YEARLY_DAYS if (kind or "").strip().lower() == "yearly" else MONTHLY_DAYS


def _kind_from_entity(entity: dict, cfg: dict, amount: int = 0) -> str:
    notes = _notes(entity)
    if notes.get("plan") in ("monthly", "yearly"):
        return notes["plan"]
    pid = str(entity.get("plan_id") or "")
    if pid and pid in (cfg.get("plan_yearly"), cfg.get("plan_yearly_usd")):
        return "yearly"
    if pid and pid in (cfg.get("plan_monthly"), cfg.get("plan_monthly_usd")):
        return "monthly"
    currency = CURRENCY_USD if pid in (cfg.get("plan_monthly_usd"), cfg.get("plan_yearly_usd")) else CURRENCY
    _days, kind = _days_for_amount(amount, "", currency=currency)
    return kind


def _rzp_get_json(cfg: dict, path: str, params: dict | None = None) -> dict | None:
    r = requests.get(f"{_RZP}{path}", params=params or {}, auth=_auth_pair(cfg), timeout=_TIMEOUT)
    if r.status_code >= 400:
        return None
    data = r.json() if r.content else {}
    return data if isinstance(data, dict) else None


def _rzp_list_items(cfg: dict, path: str, params: dict | None = None, pages: int = 3) -> list:
    out: list = []
    base = dict(params or {})
    for page in range(max(1, pages)):
        query = dict(base)
        query["count"] = 100
        query["skip"] = page * 100
        data = _rzp_get_json(cfg, path, query)
        if not data:
            break
        items = data.get("items")
        if not isinstance(items, list) or not items:
            break
        out.extend(item for item in items if isinstance(item, dict))
        if len(items) < 100:
            break
    return out


def _apply_rzp_subscription(user_id: int, cfg: dict, entity: dict) -> bool:
    if not isinstance(entity, dict):
        return False
    sub_id = str(entity.get("id") or "")
    kind = _kind_from_entity(entity, cfg)
    try:
        paid_count = int(entity.get("paid_count") or 0)
    except (TypeError, ValueError):
        paid_count = 0
    # Never grant Premium for checkout-only subscriptions (created/authenticated/pending).
    if paid_count < 1:
        return False
    until = _unix_to_dt(entity.get("current_end"))
    now = _now()
    if until is None or until <= now:
        return False
    ok = ensure_premium_until(user_id, until, billing_plan=kind, sub_id=sub_id)
    if ok and sub_id:
        db.get_conn().execute("UPDATE users SET rzp_subscription_id = ? WHERE id = ?", (sub_id, user_id))
        db.get_conn().commit()
    return ok


def _apply_captured_payment(user_id: int, cfg: dict, pay: dict, email: str = "") -> bool:
    if not isinstance(pay, dict):
        return False
    status = str(pay.get("status") or "").lower()
    if status not in ("captured", "authorized"):
        return False
    if str(pay.get("refund_status") or "").lower() in ("full", "processed"):
        return False
    try:
        amount = int(pay.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount < MONTHLY_PAISE_MIN:
        return False
    payment_id = str(pay.get("id") or "")
    notes = _notes(pay)
    kind = notes.get("plan") if notes.get("plan") in ("monthly", "yearly") else ""
    days, kind = _days_for_amount(amount, kind)
    sub_id = str(pay.get("subscription_id") or notes.get("subscription_id") or "")
    start = _unix_to_dt(pay.get("created_at")) or _now()
    if payment_id and not _claim_payment_id(user_id, payment_id, email):
        return False
    conn = db.get_conn()
    if payment_id:
        try:
            conn.execute(
                "INSERT INTO payments (user_id, razorpay_payment_id, razorpay_subscription_id, amount_paise, kind, provider, created_at) "
                "VALUES (?, ?, ?, ?, 'subscription', 'razorpay', ?)",
                (
                    user_id,
                    payment_id,
                    sub_id,
                    amount,
                    (start if start.tzinfo else start.replace(tzinfo=timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            if not _claim_payment_id(user_id, payment_id, email):
                return False
    cust = str(pay.get("customer_id") or "")
    if cust:
        conn.execute(
            "UPDATE users SET rzp_customer_id = COALESCE(NULLIF(rzp_customer_id, ''), ?) WHERE id = ?",
            (cust, user_id),
        )
        conn.commit()
    ok = ensure_premium_until(user_id, start + timedelta(days=days), billing_plan=kind, sub_id=sub_id)
    if ok:
        logger.info("Restored Premium for user %s from Razorpay payment %s", user_id, payment_id)
    return ok


def _find_rzp_customer_id(cfg: dict, email: str, stored: str = "") -> str:
    if stored:
        return stored
    if not email:
        return ""
    for entity in _rzp_list_items(cfg, "/customers"):
        if _same_mailbox(str(entity.get("email") or ""), email):
            return str(entity.get("id") or "")
    return ""


def _restore_from_razorpay(user_id: int) -> bool:
    cfg = settings()
    if not _keys_ready(cfg):
        return False
    row = db.get_conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return False
    email = str(row["email"] or "").strip()
    sub_id = str(row["rzp_subscription_id"] or "").strip()
    cust = str(row["rzp_customer_id"] or "").strip()
    has_local_pay = db.get_conn().execute(
        "SELECT 1 FROM payments WHERE user_id = ? LIMIT 1",
        (user_id,),
    ).fetchone()
    # Skip Razorpay API scans for brand-new free accounts with no billing footprint.
    if not sub_id and not cust and not has_local_pay:
        return False
    try:
        if sub_id:
            data = _rzp_get_json(cfg, f"/subscriptions/{sub_id}")
            if data and _apply_rzp_subscription(user_id, cfg, data):
                return True
        if not cust:
            cust = _find_rzp_customer_id(cfg, email, "")
            if cust:
                db.get_conn().execute("UPDATE users SET rzp_customer_id = ? WHERE id = ?", (cust, user_id))
                db.get_conn().commit()
        if cust or sub_id or has_local_pay:
            for entity in _rzp_list_items(cfg, "/subscriptions"):
                if not _belongs_to_user(entity, user_id, email, cust):
                    continue
                if _apply_rzp_subscription(user_id, cfg, entity):
                    return True
        paid_from = int((_now() - timedelta(days=40)).timestamp())
        for pay in _rzp_list_items(cfg, "/payments", {"from": paid_from}):
            if not _belongs_to_user(pay, user_id, email, cust):
                continue
            if _apply_captured_payment(user_id, cfg, pay, email):
                return True
    except requests.RequestException:
        logger.exception("Razorpay restore failed for user %s", user_id)
    return False


def _premium_entitlement_active(user_id: int) -> bool:
    """True when this account has proof of paid Premium (payment, coupon, or paid Razorpay sub)."""
    conn = db.get_conn()
    now = _now()
    for pay in conn.execute(
        "SELECT amount_paise, kind, created_at FROM payments WHERE user_id = ?",
        (user_id,),
    ):
        start = auth.parse_until(pay["created_at"])
        if not start:
            continue
        days, _kind = _days_for_amount(int(pay["amount_paise"] or 0), str(pay["kind"] or ""))
        if start + timedelta(days=days) > now:
            return True
    coupons = db.load_coupons()
    for red in conn.execute(
        "SELECT code, created_at, days FROM coupon_redemptions WHERE user_id = ?",
        (user_id,),
    ):
        start = auth.parse_until(red["created_at"])
        if not start:
            continue
        stored_days = red["days"]
        if stored_days not in (None, ""):
            try:
                days = max(1, int(stored_days))
            except (TypeError, ValueError):
                days = 0
        else:
            days = 0
        if not days:
            _stored, spec = find_coupon(coupons, str(red["code"] or ""))
            days = coupon_days(spec) if spec is not None else MONTHLY_DAYS
        if start + timedelta(days=days) > now:
            return True
    cfg = settings()
    if _keys_ready(cfg):
        row = conn.execute("SELECT rzp_subscription_id FROM users WHERE id = ?", (user_id,)).fetchone()
        sub_id = str(row["rzp_subscription_id"] or "").strip() if row else ""
        if sub_id:
            data = _rzp_get_json(cfg, f"/subscriptions/{sub_id}")
            if isinstance(data, dict):
                try:
                    paid_count = int(data.get("paid_count") or 0)
                except (TypeError, ValueError):
                    paid_count = 0
                cur_end = _unix_to_dt(data.get("current_end"))
                if paid_count >= 1 and cur_end and cur_end > now:
                    return True
    return False


def _revoke_unpaid_premium(user_id: int) -> bool:
    conn = db.get_conn()
    row = conn.execute("SELECT plan, premium_until FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or row["plan"] != "premium":
        return False
    until = auth.parse_until(row["premium_until"])
    if until is None or until <= _now():
        return False
    if _premium_entitlement_active(user_id):
        return False
    conn.execute(
        "UPDATE users SET plan = 'free', billing_plan = NULL, premium_until = NULL WHERE id = ?",
        (user_id,),
    )
    conn.commit()
    logger.info("Revoked unpaid Premium for user %s", user_id)
    return True


def repair_premium(user_id: int) -> bool:
    """If this account paid or redeemed and still has time left, put Premium back."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    if uid in _repairing:
        return False
    conn = db.get_conn()
    row = conn.execute(
        "SELECT plan, premium_until FROM users WHERE id = ?",
        (uid,),
    ).fetchone()
    if not row:
        return False
    until = auth.parse_until(row["premium_until"])
    now = _now()
    if until and until > now:
        if row["plan"] == "premium" and not _premium_entitlement_active(uid):
            _revoke_unpaid_premium(uid)
            return True
        if row["plan"] != "premium":
            conn.execute("UPDATE users SET plan = 'premium' WHERE id = ?", (uid,))
            conn.commit()
            return True
        return False
    miss_until = _repair_miss_until.get(uid)
    _repairing.add(uid)
    try:
        if _restore_from_local(uid):
            _repair_miss_until.pop(uid, None)
            return True
        if miss_until and miss_until > now:
            return False
        ok = _restore_from_razorpay(uid)
        if ok:
            _repair_miss_until.pop(uid, None)
        else:
            _repair_miss_until[uid] = now + timedelta(seconds=120)
        return ok
    except Exception:
        logger.exception("Premium repair failed for user %s", uid)
        return False
    finally:
        _repairing.discard(uid)


def _ensure_customer(user_id: int, cfg: dict) -> str:
    row = db.get_conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    existing = (row["rzp_customer_id"] or "").strip() if row else ""
    if existing:
        return existing
    try:
        r = requests.post(
            f"{_RZP}/customers",
            json={
                "name": (row["username"] if row else "") or "PyClips",
                "email": row["email"] if row else "",
                "fail_existing": "0",
            },
            auth=_auth_pair(cfg),
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Could not reach Razorpay.") from exc
    data = r.json() if r.content else {}
    if r.status_code >= 400:
        msg = (data.get("error") or {}).get("description") if isinstance(data, dict) else None
        raise HTTPException(status_code=400, detail=msg or "Razorpay rejected the customer.")
    cid = data.get("id")
    if not cid:
        raise HTTPException(status_code=502, detail="Razorpay did not return a customer id.")
    db.get_conn().execute("UPDATE users SET rzp_customer_id = ? WHERE id = ?", (cid, user_id))
    db.get_conn().commit()
    return cid


def create_subscription(user_id: int, body: SubscribeBody) -> dict:
    """Razorpay Subscriptions — INR (India) or USD (International)."""
    cfg = settings()
    kind = (body.plan or "monthly").strip().lower()
    if kind not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="Choose monthly or yearly.")
    currency = (body.currency or "").strip().upper()
    if currency not in (CURRENCY, CURRENCY_USD):
        currency = CURRENCY
    if currency == CURRENCY_USD and not razorpay_intl_ready(cfg):
        raise HTTPException(
            status_code=503,
            detail="International USD checkout is not configured yet. Enable Razorpay International and add USD plan ids.",
        )
    if currency == CURRENCY and not razorpay_ready(cfg):
        raise HTTPException(
            status_code=503,
            detail="There is some technical error with the payment system. Please try again later.",
        )
    plan_id, amount, days, currency = _plan_meta(kind, currency)
    customer_id = _ensure_customer(user_id, cfg)
    user = auth.get_user_by_id(user_id) or {}
    payload = {
        "plan_id": plan_id,
        "customer_id": customer_id,
        "quantity": 1,
        "total_count": 120 if kind == "monthly" else 20,
        "customer_notify": 1,
        "notes": {
            "user_id": str(user_id),
            "plan": kind,
            "currency": currency,
            "ticket": (body.ticket or "").strip(),
            "product": "pyclips_premium",
        },
    }
    try:
        r = requests.post(f"{_RZP}/subscriptions", json=payload, auth=_auth_pair(cfg), timeout=_TIMEOUT)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Could not reach Razorpay.") from exc
    data = r.json() if r.content else {}
    if r.status_code >= 400:
        msg = (data.get("error") or {}).get("description") if isinstance(data, dict) else None
        raise HTTPException(status_code=400, detail=msg or "Razorpay rejected the subscription.")
    sub_id = data.get("id")
    if not sub_id:
        raise HTTPException(status_code=502, detail="Razorpay did not return a subscription id.")
    if body.ticket:
        from . import tickets

        tickets.bind_ticket(body.ticket, user_id, preferred_plan=kind)
    return {
        "subscription_id": sub_id,
        "key_id": cfg["key_id"],
        "plan": kind,
        "amount": amount,
        "days": days,
        "currency": currency,
        "name": "PyClips",
        "description": (
            ("Premium monthly" if kind == "monthly" else "Premium yearly")
            + (" (USD)" if currency == CURRENCY_USD else "")
        ),
        "prefill": {"email": user.get("email") or "", "name": user.get("username") or ""},
        "theme": {"color": "#7C5CFF"},
    }


def verify_subscription(user_id: int, body: VerifySubBody) -> dict:
    cfg = settings()
    if not (razorpay_ready(cfg) or razorpay_intl_ready(cfg)):
        raise HTTPException(status_code=503, detail="Payments are not configured.")
    secret = cfg["key_secret"].encode("utf-8")
    expect = hmac.new(
        secret,
        f"{body.razorpay_payment_id}|{body.razorpay_subscription_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expect, body.razorpay_signature.strip()):
        raise HTTPException(status_code=400, detail="Payment signature did not match.")
    conn = db.get_conn()
    prior = conn.execute(
        "SELECT id FROM payments WHERE razorpay_payment_id = ?",
        (body.razorpay_payment_id,),
    ).fetchone()
    row = db.get_conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    kind = (row["billing_plan"] if row and row["billing_plan"] else "monthly")
    currency = CURRENCY
    if body.ticket:
        from . import tickets

        rec = tickets.get_ticket(body.ticket)
        if rec and rec.get("plan") in ("monthly", "yearly"):
            kind = rec["plan"]
    # Prefer plan/currency from Razorpay subscription notes when available.
    try:
        r0 = requests.get(
            f"{_RZP}/subscriptions/{body.razorpay_subscription_id}",
            auth=_auth_pair(cfg),
            timeout=_TIMEOUT,
        )
        sub0 = r0.json() if r0.content else {}
        notes0 = (sub0.get("notes") or {}) if isinstance(sub0, dict) else {}
        if notes0.get("plan") in ("monthly", "yearly"):
            kind = notes0["plan"]
        if str(notes0.get("currency") or "").upper() in (CURRENCY, CURRENCY_USD):
            currency = str(notes0["currency"]).upper()
        elif str(cfg.get("plan_yearly_usd") or "") and str(sub0.get("plan_id") or "") in (
            cfg.get("plan_yearly_usd"),
            cfg.get("plan_monthly_usd"),
        ):
            currency = CURRENCY_USD
    except requests.RequestException:
        pass
    _plan_id, amount, days, currency = _plan_meta(kind, currency)
    if prior:
        if body.ticket:
            from . import tickets

            tickets.bind_ticket(body.ticket, user_id, preferred_plan=kind)
            tickets.mark_paid_for_user(user_id)
        snap = auth.subscription_for(user_id)
        if snap.get("plan") == "premium":
            return snap
        return grant_premium(
            user_id,
            days=days,
            billing_plan=kind,
            payment_id=body.razorpay_payment_id,
            sub_id=body.razorpay_subscription_id,
            amount=amount,
            currency=currency,
        )
    try:
        r = requests.get(
            f"{_RZP}/subscriptions/{body.razorpay_subscription_id}",
            auth=_auth_pair(cfg),
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Could not confirm the subscription with Razorpay.") from exc
    sub = r.json() if r.content else {}
    if r.status_code >= 400:
        raise HTTPException(status_code=400, detail="Razorpay could not find that subscription.")
    notes = sub.get("notes") or {}
    if str(notes.get("user_id") or "") not in ("", str(user_id)):
        raise HTTPException(status_code=400, detail="That subscription belongs to another account.")
    if notes.get("plan") in ("monthly", "yearly"):
        kind = notes["plan"]
        if str(notes.get("currency") or "").upper() in (CURRENCY, CURRENCY_USD):
            currency = str(notes["currency"]).upper()
        _plan_id, amount, days, currency = _plan_meta(kind, currency)
    conn.execute(
        "UPDATE users SET rzp_subscription_id = ? WHERE id = ?",
        (body.razorpay_subscription_id, user_id),
    )
    conn.commit()
    if body.ticket:
        from . import tickets

        tickets.bind_ticket(body.ticket, user_id, preferred_plan=kind)
    return grant_premium(
        user_id,
        days=days,
        billing_plan=kind,
        payment_id=body.razorpay_payment_id,
        sub_id=body.razorpay_subscription_id,
        amount=amount,
        currency=currency,
    )


def apply_webhook(body: bytes, signature: str) -> dict:
    cfg = settings()
    secret = (cfg.get("webhook_secret") or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook secret is not set.")
    expect = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, (signature or "").strip()):
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")
    try:
        payload = json.loads(body.decode("utf-8"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook body.")
    event = payload.get("event") or ""
    bag = payload.get("payload") or {}
    sub_ent = (bag.get("subscription") or {}).get("entity") or {}
    pay_ent = (bag.get("payment") or {}).get("entity") or {}
    if not isinstance(sub_ent, dict):
        sub_ent = {}
    if not isinstance(pay_ent, dict):
        pay_ent = {}
    notes = sub_ent.get("notes") or pay_ent.get("notes") or {}
    if not isinstance(notes, dict):
        notes = {}
    sub_id = str(sub_ent.get("id") or pay_ent.get("subscription_id") or "")
    user_id = 0
    try:
        user_id = int(notes.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    if user_id and not _user_exists(user_id):
        user_id = 0
    if not user_id and sub_id:
        row = db.get_conn().execute(
            "SELECT id FROM users WHERE rzp_subscription_id = ?", (sub_id,)
        ).fetchone()
        if row:
            user_id = int(row["id"])
    if not user_id:
        email = str(
            pay_ent.get("email")
            or notes.get("email")
            or sub_ent.get("customer_email")
            or ""
        ).strip()
        if email:
            found = auth.find_user_row(db.get_conn(), email)
            if found:
                user_id = int(found["id"])
    if not user_id:
        return {"status": "ignored"}
    kind = notes.get("plan") if notes.get("plan") in ("monthly", "yearly") else "monthly"
    payment_id = str(pay_ent.get("id") or "")
    currency = str(notes.get("currency") or CURRENCY).strip().upper()
    if currency not in (CURRENCY, CURRENCY_USD):
        currency = CURRENCY
    pid = str(sub_ent.get("plan_id") or "")
    if pid and pid in (cfg.get("plan_monthly_usd"), cfg.get("plan_yearly_usd")):
        currency = CURRENCY_USD
    amount = MONTHLY_CENTS if currency == CURRENCY_USD else MONTHLY_PAISE
    try:
        _pid, amount, days, currency = _plan_meta(kind, currency)
    except HTTPException:
        days = MONTHLY_DAYS
    if pay_ent.get("amount"):
        try:
            amount = int(pay_ent["amount"])
            days, kind = _days_for_amount(amount, kind, currency=currency)
        except (TypeError, ValueError):
            pass
    paid_events = (
        "subscription.charged",
        "payment.captured",
    )
    if event in paid_events:
        if event == "subscription.charged":
            try:
                paid_count = int(sub_ent.get("paid_count") or 0)
            except (TypeError, ValueError):
                paid_count = 0
            if paid_count < 1:
                return {"status": "ignored", "event": event, "reason": "unpaid_subscription"}
        grant_premium(
            user_id,
            days=days,
            billing_plan=kind,
            payment_id=payment_id,
            sub_id=sub_id,
            amount=amount,
            currency=currency,
        )
    elif event == "subscription.cancelled":
        conn = db.get_conn()
        conn.execute("UPDATE users SET rzp_subscription_id = NULL WHERE id = ?", (user_id,))
        conn.commit()
    return {"status": "ok", "event": event}


def redeem_code(user_id: int, code: str) -> dict:
    raw = (code or "").strip()
    with db._lock:
        coupons = db.load_coupons()
        stored, spec = find_coupon(coupons, raw)
        if spec is None or coupon_archived(spec):
            raise HTTPException(status_code=400, detail="That code is not valid.")
        days = coupon_days(spec)
        cap = coupon_max_redemptions(spec)
        stamp_code = stored.upper()
        conn = db.get_conn()
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        try:
            used = conn.execute(
                "SELECT COUNT(*) AS n FROM coupon_redemptions WHERE code = ?",
                (stamp_code,),
            ).fetchone()
            if cap is not None and int(used["n"] or 0) >= cap:
                conn.rollback()
                raise HTTPException(status_code=400, detail="This code has reached its limit.")
            conn.execute(
                "INSERT INTO coupon_redemptions (user_id, code, created_at, days) VALUES (?, ?, ?, ?)",
                (user_id, stamp_code, _now().strftime("%Y-%m-%dT%H:%M:%SZ"), days),
            )
            conn.commit()
        except HTTPException:
            raise
        except sqlite3.IntegrityError:
            conn.rollback()
            raise HTTPException(status_code=400, detail="You already used that code.")
        except Exception:
            conn.rollback()
            raise
    return grant_premium(user_id, days=days, billing_plan="coupon")



def detect_currency(request: Request | None = None, override: str = "") -> str:
    """INR for India; USD for USA / other. Manual ?currency=USD|INR wins."""
    o = (override or "").strip().upper()
    if o in ("USD", "INR"):
        return o
    if request is not None:
        country = (request.headers.get("CF-IPCountry") or request.headers.get("cf-ipcountry") or "").strip().upper()
        if country == "IN":
            return CURRENCY
        if country and country not in ("XX", "T1"):
            return CURRENCY_USD
        accept = (request.headers.get("Accept-Language") or "").lower()
        if "en-in" in accept or accept.startswith("hi") or ",hi" in accept:
            return CURRENCY
    return CURRENCY_USD


def pricing_for(request: Request | None = None, currency: str = "") -> dict:
    cfg = settings()
    cur = detect_currency(request, currency)
    inr_ok = razorpay_ready(cfg)
    usd_ok = razorpay_intl_ready(cfg)
    if cur == CURRENCY:
        enabled = inr_ok
        monthly_display = "₹29"
        yearly_display = "₹199"
        monthly_label = "₹29 / month"
        yearly_label = "₹199 / year"
        amount_monthly = MONTHLY_PAISE
        amount_yearly = YEARLY_PAISE
    else:
        enabled = usd_ok
        monthly_display = "$2.99"
        yearly_display = "$29.99"
        monthly_label = "$2.99 / month"
        yearly_label = "$29.99 / year"
        amount_monthly = MONTHLY_CENTS
        amount_yearly = YEARLY_CENTS
    return {
        "currency": cur,
        "provider": "razorpay",
        "payments_enabled": enabled,
        "razorpay_enabled": inr_ok,
        "razorpay_intl_enabled": usd_ok,
        "monthly_display": monthly_display,
        "yearly_display": yearly_display,
        "monthly_label": monthly_label,
        "yearly_label": yearly_label,
        "amount_monthly": amount_monthly,
        "amount_yearly": amount_yearly,
        "price_monthly": monthly_label,
        "price_yearly": yearly_label,
        "can_override": True,
    }
