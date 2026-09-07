"""Email/password sessions for the account website."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import db
from .config import FREE_VIDEO_CAP, MONTHLY_DAYS, settings, payments_ready

COOKIE = "pyclips_site"
SESSION_DAYS = 30
_PBKDF2_ROUNDS = 210_000
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USER_RE = re.compile(r"^[a-zA-Z0-9_]{3,24}$")


class RegisterBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    username: str = Field(default="", max_length=24)
    ticket: str = Field(default="", max_length=64)


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)
    ticket: str = Field(default="", max_length=64)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _secret() -> bytes:
    path = db.secret_path()
    if path.is_file():
        return path.read_bytes()
    raw = secrets.token_bytes(32)
    path.write_bytes(raw)
    return raw


def tidy_email(email: str) -> str:
    """Lowercase and trim only. Gmail dots stay so the address matches what people type."""
    return (email or "").strip().lower()


def canonical_email(email: str) -> str:
    """Gmail mailbox identity: dots, plus-tags, and googlemail.com collapse."""
    raw = tidy_email(email)
    if "@" not in raw:
        return raw
    local, domain = raw.rsplit("@", 1)
    if domain == "googlemail.com":
        domain = "gmail.com"
    if domain == "gmail.com":
        local = local.split("+", 1)[0].replace(".", "")
    return f"{local}@{domain}"


def normalize_email(email: str) -> str:
    """Mailbox identity for matching. Not the visible address."""
    return canonical_email(email)


def find_user_rows(conn: sqlite3.Connection, email: str) -> list:
    key = canonical_email(email)
    if not key:
        return []
    return [row for row in conn.execute("SELECT * FROM users") if canonical_email(row["email"]) == key]


def find_user_row(conn: sqlite3.Connection, email: str):
    rows = find_user_rows(conn, email)
    if not rows:
        return None
    typed = tidy_email(email)
    for row in rows:
        if tidy_email(row["email"]) == typed:
            return row
    with_password = [row for row in rows if str(row["password_hash"] or "").strip()]
    if with_password:
        return max(with_password, key=_keeper_rank)
    return max(rows, key=_keeper_rank)


def _preferred_display_email(members) -> str:
    for row in members:
        local = (row["email"] or "").split("@", 1)[0]
        if "." in local:
            return tidy_email(row["email"])
    return tidy_email(members[0]["email"]) if members else ""


def _keeper_rank(row) -> tuple:
    plan = str(row["plan"] or "free")
    google = 1 if str(row["google_id"] or "").strip() else 0
    pw = 1 if str(row["password_hash"] or "").strip() else 0
    premium = 2 if plan == "premium" else 0
    return (premium, google, pw, -int(row["id"]))


def merge_duplicate_emails(conn: sqlite3.Connection) -> None:
    """Collapse Gmail aliases / duplicate rows that are the same mailbox."""
    rows = list(conn.execute("SELECT * FROM users"))
    groups: dict[str, list] = {}
    for row in rows:
        groups.setdefault(normalize_email(row["email"]), []).append(row)
    for canonical, members in groups.items():
        if not canonical or "@" not in canonical:
            continue
        keeper = max(members, key=_keeper_rank)
        kid = int(keeper["id"])
        for other in members:
            oid = int(other["id"])
            if oid == kid:
                continue
            if str(other["google_id"] or "").strip() and not str(keeper["google_id"] or "").strip():
                conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (other["google_id"], kid))
            if str(other["password_hash"] or "").strip() and not str(keeper["password_hash"] or "").strip():
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (other["password_hash"], kid))
            if str(other["plan"] or "") == "premium" and str(keeper["plan"] or "") != "premium":
                conn.execute(
                    "UPDATE users SET plan = ?, premium_until = ?, billing_plan = ?, "
                    "rzp_customer_id = COALESCE(rzp_customer_id, ?), "
                    "rzp_subscription_id = COALESCE(rzp_subscription_id, ?) WHERE id = ?",
                    (
                        other["plan"],
                        other["premium_until"],
                        other["billing_plan"],
                        other["rzp_customer_id"] if "rzp_customer_id" in other.keys() else None,
                        other["rzp_subscription_id"] if "rzp_subscription_id" in other.keys() else None,
                        kid,
                    ),
                )
            used_k = int(conn.execute("SELECT videos_used FROM users WHERE id = ?", (kid,)).fetchone()["videos_used"] or 0)
            used_o = int(other["videos_used"] or 0)
            conn.execute("UPDATE users SET videos_used = ? WHERE id = ?", (max(used_k, used_o), kid))
            conn.execute("UPDATE tickets SET user_id = ? WHERE user_id = ?", (kid, oid))
            conn.execute("UPDATE payments SET user_id = ? WHERE user_id = ?", (kid, oid))
            for red in conn.execute("SELECT code, created_at FROM coupon_redemptions WHERE user_id = ?", (oid,)):
                conn.execute(
                    "INSERT OR IGNORE INTO coupon_redemptions (user_id, code, created_at) VALUES (?, ?, ?)",
                    (kid, red["code"], red["created_at"]),
                )
            conn.execute("DELETE FROM coupon_redemptions WHERE user_id = ?", (oid,))
            conn.execute("DELETE FROM users WHERE id = ?", (oid,))
        display = _preferred_display_email(members)
        current = conn.execute("SELECT email FROM users WHERE id = ?", (kid,)).fetchone()
        if display and current and current["email"] != display:
            try:
                conn.execute("UPDATE users SET email = ? WHERE id = ?", (display, kid))
            except sqlite3.IntegrityError:
                pass
    conn.commit()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"{salt.hex()}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    return hmac.compare_digest(_hash_password(password, salt), stored)


def _username_from_email(email: str) -> str:
    local = (email or "").split("@", 1)[0]
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "", local)[:24]
    if len(cleaned) < 3:
        cleaned = (cleaned + "user")[:8]
    return cleaned.lower()


def allocate_username(conn: sqlite3.Connection, preferred: str, exclude_id: Optional[int] = None) -> str:
    base = (preferred or "").strip()
    if not _USER_RE.match(base):
        base = _username_from_email(preferred) if "@" in preferred else re.sub(r"[^a-zA-Z0-9_]", "", base)[:24]
        if len(base) < 3:
            base = (base + "user")[:8]
        base = base.lower()
    cand = base
    n = 1
    while True:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (cand,)).fetchone()
        if row is None or (exclude_id is not None and int(row["id"]) == exclude_id):
            return cand
        n += 1
        cand = f"{base[:20]}{n}"


def public_user(row) -> dict:
    plan = row["plan"] if row["plan"] else "free"
    return {
        "id": int(row["id"]),
        "email": row["email"],
        "username": row["username"] or _username_from_email(row["email"]),
        "plan": plan,
    }


def parse_until(raw: Optional[str]):
    if not raw:
        return None
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def expire_if_needed(user_id: int) -> None:
    conn = db.get_conn()
    row = conn.execute("SELECT plan, premium_until FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or row["plan"] != "premium":
        return
    until = parse_until(row["premium_until"])
    if until is None or until > datetime.now(timezone.utc):
        return
    # Keep rzp_subscription_id so webhooks / repair can restore the next paid period.
    conn.execute(
        "UPDATE users SET plan = 'free', billing_plan = NULL WHERE id = ?",
        (user_id,),
    )
    conn.commit()


def get_user_by_id(user_id: int) -> Optional[dict]:
    from . import billing

    billing.repair_premium(user_id)
    expire_if_needed(user_id)
    row = db.get_conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return public_user(row) if row else None


def get_user_row(user_id: int):
    from . import billing

    billing.repair_premium(user_id)
    expire_if_needed(user_id)
    return db.get_conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def subscription_for(user_id: int, request: Request | None = None) -> dict:
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in.")
    row = get_user_row(user_id)
    used = int(row["videos_used"] or 0)
    premium = user["plan"] == "premium"
    until = parse_until(row["premium_until"] if row else None)
    days_left = None
    if premium and until:
        secs = (until - datetime.now(timezone.utc)).total_seconds()
        days_left = max(0, int((secs + 86399) // 86400)) if secs > 0 else 0
    cfg = settings()
    from . import billing as billing_mod

    prices = billing_mod.pricing_for(request)
    autopay = bool(row["rzp_subscription_id"] if row else None)
    return {
        "plan": user["plan"],
        "billing_plan": row["billing_plan"] if row else None,
        "username": user["username"],
        "email": user["email"],
        "videos_used": used,
        "videos_limit": None if premium else FREE_VIDEO_CAP,
        "unlimited": premium,
        "premium_until": until.strftime("%Y-%m-%dT%H:%M:%SZ") if until and premium else None,
        "days_left": days_left,
        "price_monthly": prices["price_monthly"],
        "price_yearly": prices["price_yearly"],
        "currency": prices["currency"],
        "provider": prices["provider"],
        "monthly_display": prices["monthly_display"],
        "yearly_display": prices["yearly_display"],
        "period_days": MONTHLY_DAYS,
        "payments_enabled": payments_ready(cfg),
        "razorpay_enabled": prices["razorpay_enabled"],
        "razorpay_intl_enabled": prices["razorpay_intl_enabled"],
        "test_mode": str(cfg.get("key_id") or "").startswith("rzp_test_"),
        "autopay": autopay,
    }


def create_user(email: str, password: str, username: str = "") -> dict:
    stored = tidy_email(email)
    if not _EMAIL_RE.match(stored):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    conn = db.get_conn()
    if find_user_row(conn, stored):
        raise HTTPException(
            status_code=409,
            detail="An account with that email already exists. Log in instead.",
        )
    if (username or "").strip():
        if not _USER_RE.match(username.strip()):
            raise HTTPException(
                status_code=400,
                detail="Username must be 3–24 characters: letters, numbers, underscore.",
            )
        name = username.strip()
        if conn.execute("SELECT id FROM users WHERE username = ?", (name,)).fetchone():
            raise HTTPException(status_code=409, detail="That username is already taken.")
    else:
        name = allocate_username(conn, stored)
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, username, plan, created_at) VALUES (?, ?, ?, 'free', ?)",
            (stored, _hash_password(password), name, _now_iso()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="An account with that email or username already exists.")
    row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return public_user(row)


def authenticate(email: str, password: str) -> dict:
    typed = tidy_email(email)
    conn = db.get_conn()
    rows = find_user_rows(conn, typed)
    if not rows:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    matched = None
    for row in rows:
        stored_hash = (row["password_hash"] or "").strip()
        if stored_hash and _verify_password(password, stored_hash):
            matched = row
            break
    if matched is None:
        if all(not str(row["password_hash"] or "").strip() for row in rows):
            raise HTTPException(
                status_code=401,
                detail="This account uses Google. Click Continue with Google.",
            )
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    matched = _restore_typed_gmail(conn, matched, typed)
    return public_user(matched)


def _restore_typed_gmail(conn: sqlite3.Connection, row, typed: str):
    """If they signed in with dots and we stored the collapsed form, put the dots back."""
    typed = tidy_email(typed)
    stored = tidy_email(row["email"] or "")
    if canonical_email(typed) != canonical_email(stored):
        return row
    typed_local = typed.split("@", 1)[0]
    stored_local = stored.split("@", 1)[0]
    if "." in typed_local and "." not in stored_local:
        try:
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (typed, int(row["id"])))
            conn.commit()
            fresh = conn.execute("SELECT * FROM users WHERE id = ?", (int(row["id"]),)).fetchone()
            return fresh or row
        except sqlite3.IntegrityError:
            conn.rollback()
    return row


def upsert_google_user(google_id: str, email: str, display_name: str = "") -> dict:
    google_id = (google_id or "").strip()
    stored = tidy_email(email)
    if not google_id or not _EMAIL_RE.match(stored):
        raise HTTPException(status_code=400, detail="Google did not share a valid email.")
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    if row is None:
        row = find_user_row(conn, stored)
        if row is not None:
            conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, row["id"]))
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
    if row is None:
        name = allocate_username(conn, display_name or stored)
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, username, plan, google_id, created_at) VALUES (?, '', ?, 'free', ?, ?)",
            (stored, name, google_id, _now_iso()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return public_user(row)


def set_session_cookie(resp: Response, user: dict) -> None:
    payload = f"{user['id']}|{int(datetime.now(timezone.utc).timestamp())}"
    sig = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    from .config import settings

    secure = settings()["public_url"].startswith("https://")
    resp.set_cookie(
        COOKIE,
        f"{payload}|{sig}",
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session(resp: Response) -> None:
    resp.delete_cookie(COOKIE, path="/")


def user_from_request(request: Request) -> Optional[dict]:
    raw = request.cookies.get(COOKIE) or ""
    parts = raw.split("|")
    if len(parts) != 3:
        return None
    uid, ts, sig = parts
    payload = f"{uid}|{ts}"
    expect = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return None
    try:
        user_id = int(uid)
    except ValueError:
        return None
    return get_user_by_id(user_id)


def current_user(request: Request) -> dict:
    user = user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user
