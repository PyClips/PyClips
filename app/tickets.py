"""Desktop checkout tickets: Chrome pays on the website, the app claims Premium."""

from __future__ import annotations

import secrets
import time
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import auth, db
from .config import settings


class BeginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    videos_used: int = Field(default=0, ge=0, le=1_000_000)
    plan: str = Field(default="monthly", max_length=16)


class UsageBody(BaseModel):
    token: str = Field(min_length=8, max_length=128)
    videos_used: int = Field(ge=0, le=1_000_000)


class DesktopRedeemBody(BaseModel):
    code: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=3, max_length=254)
    token: str = Field(default="", max_length=128)


def begin(body: BeginBody) -> dict:
    email = auth.normalize_email(body.email)
    plan = (body.plan or "monthly").strip().lower()
    if plan not in ("monthly", "yearly"):
        plan = "monthly"
    ticket = secrets.token_urlsafe(18)
    exp = int(time.time()) + 1800
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO tickets (ticket, email, plan, videos_used, status, exp) VALUES (?, ?, ?, ?, 'pending', ?)",
        (ticket, email, plan, int(body.videos_used), exp),
    )
    row = auth.find_user_row(conn, email)
    if row:
        used = max(int(row["videos_used"] or 0), int(body.videos_used))
        conn.execute("UPDATE users SET videos_used = ? WHERE id = ?", (used, row["id"]))
    conn.commit()
    cfg = settings()
    return {
        "ticket": ticket,
        "url": f"{cfg['public_url']}/pay?ticket={ticket}&plan={plan}",
    }


def get_ticket(ticket: str) -> Optional[dict]:
    ticket = (ticket or "").strip()
    if not ticket:
        return None
    row = db.get_conn().execute("SELECT * FROM tickets WHERE ticket = ?", (ticket,)).fetchone()
    if not row:
        return None
    return dict(row)


def bind_ticket(ticket: str, user_id: int, preferred_plan: str = "") -> None:
    rec = get_ticket(ticket)
    if not rec:
        return
    if int(rec["exp"]) < int(time.time()):
        return
    plan = preferred_plan or rec.get("plan") or "monthly"
    conn = db.get_conn()
    email_row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    bound_email = email_row["email"] if email_row else rec.get("email") or ""
    conn.execute(
        "UPDATE tickets SET user_id = ?, plan = ?, email = ? WHERE ticket = ?",
        (user_id, plan, bound_email, ticket),
    )
    row = conn.execute("SELECT email, videos_used FROM users WHERE id = ?", (user_id,)).fetchone()
    used = max(int(rec.get("videos_used") or 0), int(row["videos_used"] or 0) if row else 0)
    conn.execute("UPDATE users SET videos_used = ? WHERE id = ?", (used, user_id))
    conn.commit()


def mark_paid_for_user(user_id: int) -> None:
    conn = db.get_conn()
    token = secrets.token_urlsafe(24)
    later = int(time.time()) + 86400
    conn.execute(
        "UPDATE tickets SET status = 'paid', sync_token = COALESCE(NULLIF(sync_token, ''), ?), exp = ? "
        "WHERE user_id = ? AND status IN ('pending', 'paid')",
        (token, later, user_id),
    )
    pending_email = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    if pending_email:
        conn.execute(
            "UPDATE tickets SET status = 'paid', user_id = ?, sync_token = COALESCE(NULLIF(sync_token, ''), ?), exp = ? "
            "WHERE email = ? AND status = 'pending'",
            (user_id, token, later, pending_email["email"]),
        )
    conn.commit()


def claim(ticket: str) -> dict:
    rec = get_ticket(ticket)
    if not rec:
        raise HTTPException(status_code=404, detail="Sign-in expired. Open Purchase Premium again.")
    if int(rec["exp"]) < int(time.time()) and rec["status"] != "paid":
        raise HTTPException(status_code=404, detail="Checkout expired. Try again.")
    if rec["status"] != "paid":
        return {"status": "waiting"}
    uid = rec.get("user_id")
    if not uid:
        row = auth.find_user_row(db.get_conn(), rec["email"])
        uid = int(row["id"]) if row else 0
    if not uid:
        return {"status": "waiting"}
    sub = auth.subscription_for(int(uid))
    token = rec.get("sync_token") or ""
    if not token:
        token = secrets.token_urlsafe(24)
        db.get_conn().execute("UPDATE tickets SET sync_token = ? WHERE ticket = ?", (token, ticket))
        db.get_conn().commit()
    return {
        "status": "ok",
        "sync_token": token,
        "email": sub["email"],
        "plan": sub["plan"],
        "billing_plan": sub.get("billing_plan"),
        "premium_until": sub.get("premium_until"),
        "videos_used": sub["videos_used"],
        "unlimited": sub["unlimited"],
    }


def peek(ticket: str) -> dict:
    rec = get_ticket(ticket)
    if not rec or int(rec["exp"]) < int(time.time()):
        raise HTTPException(status_code=404, detail="Checkout expired.")
    return {"email": rec["email"], "plan": rec["plan"], "status": rec["status"]}


def push_usage(body: UsageBody) -> dict:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT user_id FROM tickets WHERE sync_token = ? AND user_id IS NOT NULL ORDER BY exp DESC LIMIT 1",
        (body.token.strip(),),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Unknown desktop link.")
    uid = int(row["user_id"])
    cur = conn.execute("SELECT videos_used FROM users WHERE id = ?", (uid,)).fetchone()
    used = max(int(cur["videos_used"] or 0) if cur else 0, int(body.videos_used))
    conn.execute("UPDATE users SET videos_used = ? WHERE id = ?", (used, uid))
    conn.commit()
    return auth.subscription_for(uid)


def refresh_by_token(token: str) -> dict:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT user_id FROM tickets WHERE sync_token = ? AND user_id IS NOT NULL ORDER BY exp DESC LIMIT 1",
        ((token or "").strip(),),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Unknown desktop link.")
    return auth.subscription_for(int(row["user_id"]))


def ensure_desktop_sync_token(user_id: int) -> str:
    conn = db.get_conn()
    row = conn.execute(
        "SELECT sync_token FROM tickets WHERE user_id = ? AND IFNULL(sync_token, '') != '' "
        "ORDER BY exp DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row and row["sync_token"]:
        return str(row["sync_token"])
    token = secrets.token_urlsafe(24)
    ticket = secrets.token_urlsafe(18)
    exp = int(time.time()) + 86400 * 400
    email_row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    email = email_row["email"] if email_row else ""
    conn.execute(
        "INSERT INTO tickets (ticket, email, plan, videos_used, status, exp, user_id, sync_token) "
        "VALUES (?, ?, 'desktop-sync', 0, 'paid', ?, ?, ?)",
        (ticket, email, exp, user_id, token),
    )
    conn.commit()
    return token


def refresh_by_email(email: str) -> dict:
    """Email-only license lookup is disabled. Use a desktop sync token."""
    raise HTTPException(
        status_code=401,
        detail="Desktop sync requires a signed-in desktop link.",
    )


def redeem_for_desktop(body: DesktopRedeemBody) -> dict:
    email = auth.normalize_email(body.email)
    token = (body.token or "").strip()
    if len(token) < 8:
        raise HTTPException(
            status_code=401,
            detail="Redeem from PyClips after you sign in, or redeem on pyclips.in while logged in.",
        )
    row = db.get_conn().execute(
        "SELECT user_id FROM tickets WHERE sync_token = ? AND user_id IS NOT NULL ORDER BY exp DESC LIMIT 1",
        (token,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Unknown desktop link.")
    uid = int(row["user_id"])
    user_row = db.get_conn().execute("SELECT email FROM users WHERE id = ?", (uid,)).fetchone()
    if not user_row:
        raise HTTPException(status_code=404, detail="No PyClips account for this desktop link.")
    if email and auth.normalize_email(email) != auth.normalize_email(user_row["email"]):
        raise HTTPException(status_code=400, detail="That code is for a different email.")
    from . import billing

    sub = billing.redeem_code(uid, body.code)
    sync = ensure_desktop_sync_token(uid)
    return {**sub, "sync_token": sync}


def begin_login() -> dict:
    ticket = secrets.token_urlsafe(18)
    exp = int(time.time()) + 600
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO tickets (ticket, email, plan, videos_used, status, exp) VALUES (?, '', 'login', 0, 'pending', ?)",
        (ticket, exp),
    )
    conn.commit()
    cfg = settings()
    return {
        "ticket": ticket,
        "url": f"{cfg['public_url']}/api/auth/google?ticket={ticket}",
    }


def login_claim(ticket: str) -> dict:
    rec = get_ticket(ticket)
    if not rec:
        raise HTTPException(status_code=404, detail="Sign-in expired. Try Google again.")
    if int(rec["exp"]) < int(time.time()):
        raise HTTPException(status_code=404, detail="Sign-in expired. Try Google again.")
    uid = rec.get("user_id")
    if not uid:
        return {"status": "waiting"}
    row = db.get_conn().execute("SELECT * FROM users WHERE id = ?", (int(uid),)).fetchone()
    if not row:
        return {"status": "waiting"}
    sub = auth.subscription_for(int(uid))
    token = ensure_desktop_sync_token(int(uid))
    return {
        "status": "ok",
        "email": row["email"],
        "username": row["username"] or "",
        "google_id": row["google_id"] or "",
        "videos_used": sub["videos_used"],
        "plan": sub["plan"],
        "premium_until": sub.get("premium_until"),
        "unlimited": sub["unlimited"],
        "sync_token": token,
    }
