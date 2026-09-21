"""Locked coupon admin. Password lives in PYCLIPS_ADMIN_PASSWORD only."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

from . import auth, db
from .config import storage_status

logger = logging.getLogger(__name__)

COOKIE = "pyclips_admin"
ADMIN_SECONDS = 2 * 3600
_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_CUSTOM_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$")


class AdminLoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class CreateCouponBody(BaseModel):
    months: int = Field(ge=1, le=24)
    max_people: int = Field(ge=1, le=10_000)
    code: str = Field(default="", max_length=32)


class DeleteCouponBody(BaseModel):
    code: str = Field(min_length=3, max_length=64)


class SetDownloadBody(BaseModel):
    url: str = Field(min_length=12, max_length=2048)


class SetDownloadHitsBody(BaseModel):
    hits: int = Field(ge=0, le=1_000_000_000)


class UpdateUserBody(BaseModel):
    email: Optional[str] = Field(default=None, max_length=254)
    username: Optional[str] = Field(default=None, max_length=24)
    plan: Optional[str] = Field(default=None, max_length=16)
    billing_plan: Optional[str] = Field(default=None, max_length=32)
    videos_used: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    premium_until: Optional[str] = Field(default=None, max_length=40)


def admin_password() -> str:
    return (os.environ.get("PYCLIPS_ADMIN_PASSWORD") or "").strip()


def admin_configured() -> bool:
    return bool(admin_password())


def _unavailable() -> None:
    raise HTTPException(status_code=404, detail="Not found.")


def set_admin_cookie(resp: Response) -> None:
    exp = int(time.time()) + ADMIN_SECONDS
    payload = str(exp)
    sig = hmac.new(auth._secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    from .config import settings

    secure = settings()["public_url"].startswith("https://")
    resp.set_cookie(
        COOKIE,
        f"{payload}.{sig}",
        max_age=ADMIN_SECONDS,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_admin_cookie(resp: Response) -> None:
    resp.delete_cookie(COOKIE, path="/")


def admin_from_request(request: Request) -> bool:
    if not admin_configured():
        return False
    raw = request.cookies.get(COOKIE) or ""
    if "." not in raw:
        return False
    payload, sig = raw.rsplit(".", 1)
    expect = hmac.new(auth._secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return False
    try:
        exp = int(payload)
    except ValueError:
        return False
    return exp >= int(time.time())


def require_admin(request: Request) -> None:
    if not admin_configured():
        _unavailable()
    if not admin_from_request(request):
        raise HTTPException(status_code=401, detail="Admin login required.")


def login(body: AdminLoginBody, response: Response) -> dict:
    if not admin_configured():
        _unavailable()
    given = hashlib.sha256((body.password or "").encode("utf-8")).digest()
    expected = hashlib.sha256(admin_password().encode("utf-8")).digest()
    if not hmac.compare_digest(given, expected):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    set_admin_cookie(response)
    return {"status": "ok"}


def _new_code(existing: dict) -> str:
    keys = {str(k).upper() for k in existing.keys()}
    for _ in range(64):
        left = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
        right = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
        code = f"PYCLIPS-{left}-{right}"
        if code not in keys:
            return code
    raise HTTPException(status_code=500, detail="Could not create a code. Try again.")


def _normalize_custom_code(raw: str, existing: dict) -> str:
    code = (raw or "").strip()
    if not _CUSTOM_CODE.match(code):
        raise HTTPException(
            status_code=400,
            detail="Use 3–32 letters, numbers, hyphen or underscore. Example: Sourav15",
        )
    from . import billing

    stored, spec = billing.find_coupon(existing, code)
    if spec is not None and not billing.coupon_archived(spec):
        raise HTTPException(status_code=400, detail="That code already exists.")
    return stored if spec is not None else code


def _months_for_spec(spec) -> Optional[int]:
    if isinstance(spec, dict) and spec.get("months"):
        try:
            return int(spec["months"])
        except (TypeError, ValueError):
            return None
    if isinstance(spec, dict) and spec.get("days"):
        try:
            days = int(spec["days"])
        except (TypeError, ValueError):
            return None
        return max(1, days // 30)
    if isinstance(spec, (int, float)):
        return max(1, int(spec) // 30)
    return None


def _days_for_spec(spec) -> int:
    from . import billing

    return billing.coupon_days(spec)


def _max_for_spec(spec) -> Optional[int]:
    if not isinstance(spec, dict):
        return None
    if "max_redemptions" not in spec or spec.get("max_redemptions") in (None, ""):
        return None
    try:
        n = int(spec["max_redemptions"])
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def list_coupons() -> dict:
    coupons = db.load_coupons()
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT code, COUNT(*) AS n FROM coupon_redemptions GROUP BY code"
    ).fetchall()
    from . import billing

    used_map = {str(r["code"]).upper(): int(r["n"] or 0) for r in rows}
    out = []
    for raw_key, spec in coupons.items():
        code = str(raw_key)
        out.append(
            {
                "code": code,
                "months": _months_for_spec(spec),
                "days": _days_for_spec(spec),
                "max_redemptions": _max_for_spec(spec),
                "used": used_map.get(code.upper(), 0),
                "archived": billing.coupon_archived(spec),
            }
        )
    out.sort(key=lambda row: row["code"])
    return {"coupons": out, "storage": storage_status()}


def create_coupon(body: CreateCouponBody) -> dict:
    months = int(body.months)
    max_people = int(body.max_people)
    days = months * 30
    with db._lock:
        coupons = dict(db.load_coupons())
        custom = (body.code or "").strip()
        code = _normalize_custom_code(custom, coupons) if custom else _new_code(coupons)
        coupons[code] = {
            "days": days,
            "months": months,
            "max_redemptions": max_people,
        }
        try:
            db.save_coupons(coupons)
        except OSError:
            raise HTTPException(status_code=500, detail="Could not save that code.") from None
    logger.info("Created redeem code %s (%s month(s), max %s people)", code, months, max_people)
    return {
        "code": code,
        "months": months,
        "days": days,
        "max_redemptions": max_people,
        "used": 0,
    }


def delete_coupon(body: DeleteCouponBody) -> dict:
    raw = (body.code or "").strip()
    with db._lock:
        from . import billing

        coupons = dict(db.load_coupons())
        stored, spec = billing.find_coupon(coupons, raw)
        if spec is None:
            raise HTTPException(status_code=404, detail="That code is not in the list.")
        kept = dict(spec) if isinstance(spec, dict) else {"days": billing.coupon_days(spec)}
        kept["archived"] = True
        coupons[stored] = kept
        try:
            db.save_coupons(coupons)
        except OSError:
            raise HTTPException(status_code=500, detail="Could not delete that code.") from None
    return {"status": "ok", "code": stored}


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path or ""
    name = Path(unquote(path)).name
    return name if name.lower().endswith(".exe") else ""


def normalize_github_exe_url(raw: str) -> str:
    url = (raw or "").strip()
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if parsed.scheme != "https" or host not in ("github.com", "www.github.com"):
        raise HTTPException(
            status_code=400,
            detail="Use a GitHub Releases download URL (https://github.com/.../releases/download/...).",
        )
    if parsed.username or parsed.password or parsed.params:
        raise HTTPException(status_code=400, detail="That download URL is not valid.")
    path = parsed.path or ""
    if "/releases/download/" not in path:
        raise HTTPException(
            status_code=400,
            detail="Use a GitHub Releases download URL (https://github.com/.../releases/download/...).",
        )
    if not path.lower().endswith(".exe"):
        raise HTTPException(status_code=400, detail="The file must be a .exe.")
    return f"https://github.com{path}"


def _download_payload(url: str, updated_at: str) -> dict:
    return {
        "url": url,
        "filename": _filename_from_url(url),
        "updated_at": updated_at,
        "public_url": "/download",
        "hits": db.get_download_hits(),
    }


def get_download() -> dict:
    row = db.get_setting(db.WINDOWS_EXE_KEY)
    if not row or not (row.get("value") or "").strip():
        return {
            "url": "",
            "filename": "",
            "updated_at": "",
            "public_url": "/download",
            "hits": db.get_download_hits(),
        }
    return _download_payload(row["value"], row.get("updated_at") or "")


def set_download(body: SetDownloadBody) -> dict:
    url = normalize_github_exe_url(body.url)
    saved = db.set_setting(db.WINDOWS_EXE_KEY, url)
    logger.info("Windows download URL set to %s", url)
    return _download_payload(url, saved["updated_at"])


def clear_download() -> dict:
    db.delete_setting(db.WINDOWS_EXE_KEY)
    return {
        "url": "",
        "filename": "",
        "updated_at": "",
        "public_url": "/download",
        "hits": db.get_download_hits(),
    }


def public_download() -> dict:
    row = db.get_setting(db.WINDOWS_EXE_KEY)
    url = (row or {}).get("value") or ""
    if not url.strip():
        return {"available": False, "url": ""}
    return {"available": True, "url": "/download"}


def windows_exe_target() -> str:
    row = db.get_setting(db.WINDOWS_EXE_KEY)
    url = ((row or {}).get("value") or "").strip()
    if not url:
        raise HTTPException(status_code=404, detail="Download is not available yet.")
    return url


def record_download_hit() -> int:
    return db.increment_download_hits()


def set_download_hits(body: SetDownloadHitsBody) -> dict:
    hits = db.set_download_hits(body.hits)
    return {"hits": hits}


def overview() -> dict:
    conn = db.get_conn()
    accounts = int(conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"])
    google = int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE google_id IS NOT NULL AND TRIM(google_id) != ''"
        ).fetchone()["n"]
    )
    premium = int(conn.execute("SELECT COUNT(*) AS n FROM users WHERE plan = 'premium'").fetchone()["n"])
    payments = int(conn.execute("SELECT COUNT(*) AS n FROM payments").fetchone()["n"])
    return {
        "accounts": accounts,
        "google_logins": google,
        "email_logins": max(0, accounts - google),
        "premium": premium,
        "free": max(0, accounts - premium),
        "website_downloads": db.get_download_hits(),
        "payments": payments,
        "storage": storage_status(),
        "notes": [
            "Accounts are people who signed in on pyclips.in (Google or email).",
            "Website downloads count clicks on pyclips.in/download after this counter started. Earlier clicks are not stored.",
            "Microsoft Store installs are only in Partner Center. They are not in this database.",
        ],
    }


def _admin_user(row) -> dict:
    google_id = str(row["google_id"] or "").strip()
    has_password = bool(str(row["password_hash"] or "").strip())
    if google_id:
        sign_in = "Google"
    elif has_password:
        sign_in = "Email"
    else:
        sign_in = "Unknown"
    until = row["premium_until"]
    return {
        "id": int(row["id"]),
        "email": row["email"] or "",
        "username": row["username"] or "",
        "plan": row["plan"] or "free",
        "billing_plan": row["billing_plan"] or "",
        "videos_used": int(row["videos_used"] or 0),
        "premium_until": until or "",
        "google": bool(google_id),
        "sign_in": sign_in,
        "created_at": row["created_at"] or "",
        "rzp_customer_id": row["rzp_customer_id"] or "",
        "rzp_subscription_id": row["rzp_subscription_id"] or "",
    }


def _get_user_or_404(user_id: int):
    row = db.get_conn().execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="That account was not found.")
    return row


def list_users(q: str = "", plan: str = "all", limit: int = 100, offset: int = 0) -> dict:
    limit = min(max(int(limit), 1), 500)
    offset = max(int(offset), 0)
    plan_key = (plan or "all").strip().lower()
    if plan_key not in ("all", "premium", "free"):
        raise HTTPException(status_code=400, detail="Plan filter must be all, premium, or free.")
    needle = (q or "").strip().lower()
    conn = db.get_conn()
    clauses: list[str] = []
    args: list = []
    if needle:
        like = f"%{needle}%"
        clauses.append("(lower(email) LIKE ? OR lower(COALESCE(username, '')) LIKE ?)")
        args.extend([like, like])
    if plan_key == "premium":
        clauses.append("plan = 'premium'")
    elif plan_key == "free":
        clauses.append("(plan IS NULL OR TRIM(plan) = '' OR plan != 'premium')")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = int(conn.execute(f"SELECT COUNT(*) AS n FROM users {where}", args).fetchone()["n"])
    rows = conn.execute(
        f"""SELECT * FROM users {where}
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ? OFFSET ?""",
        (*args, limit, offset),
    ).fetchall()
    return {
        "users": [_admin_user(row) for row in rows],
        "total": total,
        "plan": plan_key,
        "limit": limit,
        "offset": offset,
    }


def _parse_admin_until(raw: Optional[str]) -> Optional[str]:
    text = (raw or "").strip()
    if not text:
        return None
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = f"{text}T23:59:59Z"
    until = auth.parse_until(text)
    if until is None:
        raise HTTPException(status_code=400, detail="Premium until must be a date (YYYY-MM-DD).")
    return until.strftime("%Y-%m-%dT%H:%M:%SZ")


def update_user(user_id: int, body: UpdateUserBody) -> dict:
    data = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
    _get_user_or_404(user_id)
    conn = db.get_conn()
    fields: list[str] = []
    args: list = []
    if "email" in data:
        stored = auth.tidy_email(data.get("email") or "")
        if not auth._EMAIL_RE.match(stored):
            raise HTTPException(status_code=400, detail="Enter a valid email address.")
        other = auth.find_user_row(conn, stored)
        if other is not None and int(other["id"]) != int(user_id):
            raise HTTPException(status_code=409, detail="Another account already uses that email.")
        fields.append("email = ?")
        args.append(stored)
    if "username" in data:
        name = (data.get("username") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Username cannot be empty.")
        if not auth._USER_RE.match(name):
            raise HTTPException(
                status_code=400,
                detail="Username must be 3–24 characters: letters, numbers, underscore.",
            )
        taken = conn.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (name, int(user_id)),
        ).fetchone()
        if taken:
            raise HTTPException(status_code=409, detail="That username is already taken.")
        fields.append("username = ?")
        args.append(name)
    if "plan" in data:
        plan = (data.get("plan") or "").strip().lower()
        if plan not in ("free", "premium"):
            raise HTTPException(status_code=400, detail="Plan must be free or premium.")
        fields.append("plan = ?")
        args.append(plan)
    if "billing_plan" in data:
        billing_plan = (data.get("billing_plan") or "").strip().lower()
        if billing_plan in ("", "none"):
            billing_plan = None
        elif billing_plan not in ("monthly", "yearly", "coupon", "admin"):
            raise HTTPException(
                status_code=400,
                detail="Billing plan must be monthly, yearly, coupon, admin, or empty.",
            )
        fields.append("billing_plan = ?")
        args.append(billing_plan)
    if "videos_used" in data:
        fields.append("videos_used = ?")
        args.append(int(data["videos_used"]))
    if "premium_until" in data:
        fields.append("premium_until = ?")
        args.append(_parse_admin_until(data.get("premium_until")))
    # This route is an admin grant. Stamp billing_plan=admin whenever Premium is
    # saved here, otherwise repair_premium treats it as unpaid and wipes the row.
    current = _get_user_or_404(user_id)
    next_plan = str((data.get("plan") if "plan" in data else current["plan"]) or "free").strip().lower()
    if next_plan == "premium" and ("plan" in data or "billing_plan" in data or "premium_until" in data):
        if "billing_plan = ?" in fields:
            args[fields.index("billing_plan = ?")] = "admin"
        else:
            fields.append("billing_plan = ?")
            args.append("admin")
    elif next_plan == "free" and "plan" in data:
        if "billing_plan = ?" not in fields:
            fields.append("billing_plan = ?")
            args.append(None)
        elif (data.get("billing_plan") or "").strip().lower() in ("", "none", "admin"):
            args[fields.index("billing_plan = ?")] = None
    if not fields:
        return _admin_user(_get_user_or_404(user_id))
    args.append(int(user_id))
    try:
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", args)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="That email or username is already taken.") from None
    return _admin_user(_get_user_or_404(user_id))


def delete_user(user_id: int) -> dict:
    row = _get_user_or_404(user_id)
    uid = int(row["id"])
    conn = db.get_conn()
    conn.execute("DELETE FROM coupon_redemptions WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM payments WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM tickets WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    return {"status": "ok", "id": uid}
