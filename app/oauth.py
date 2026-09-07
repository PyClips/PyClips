"""Google sign-in for the account website (same Google app as the desktop client)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from typing import Optional
from urllib.parse import urlencode

import requests
from fastapi import HTTPException, Request
from starlette.responses import HTMLResponse, RedirectResponse

from . import auth, tickets
from .config import ROOT, settings

logger = logging.getLogger(__name__)

_TIMEOUT = 20
_PENDING: dict[str, dict] = {}
_LOCK = threading.Lock()
_GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
_GOOGLE_USER = "https://openidconnect.googleapis.com/v1/userinfo"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def load_google_config() -> dict:
    cfg = {"google_client_id": "", "google_client_secret": ""}
    desktop = ROOT.parent / "data" / "oauth.json"
    if desktop.is_file():
        try:
            data = json.loads(desktop.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg["google_client_id"] = str(data.get("google_client_id") or "").strip()
                cfg["google_client_secret"] = str(data.get("google_client_secret") or "").strip()
        except (OSError, ValueError):
            logger.warning("Could not read desktop data/oauth.json")
    env_id = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    env_sec = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    if env_id:
        cfg["google_client_id"] = env_id
    if env_sec:
        cfg["google_client_secret"] = env_sec
    cfg["public_url"] = settings()["public_url"]
    return cfg


def google_ready() -> bool:
    cfg = load_google_config()
    return bool(cfg["google_client_id"] and cfg["google_client_secret"])


def _redirect_uri(cfg: dict) -> str:
    return f"{cfg['public_url']}/api/auth/google/callback"


def start_google(ticket: str = "", hint: str = "") -> RedirectResponse:
    cfg = load_google_config()
    if not google_ready():
        raise HTTPException(
            status_code=503,
            detail="Google login is not set up. Add google_client_id and google_client_secret (same values as the PyClips app).",
        )
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    nonce = secrets.token_urlsafe(24)
    params = {
        "client_id": cfg["google_client_id"],
        "response_type": "code",
        "redirect_uri": _redirect_uri(cfg),
        "state": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    hint = (hint or "").strip()
    if hint:
        params["login_hint"] = hint
    url = f"{_GOOGLE_AUTH}?{urlencode(params)}"
    with _LOCK:
        _PENDING[nonce] = {
            "v": verifier,
            "exp": int(time.time()) + 600,
            "ticket": (ticket or "").strip(),
        }
    return RedirectResponse(url=url, status_code=302)


def _done_html() -> HTMLResponse:
    html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><title>PyClips</title>
<link rel="icon" href="/favicon.ico"/>
<style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0B0D10;color:#F2F4F7;
font-family:Segoe UI,system-ui,sans-serif}
.card{max-width:420px;padding:32px;border:1px solid color-mix(in srgb,#F2F4F7 14%,transparent);border-radius:16px;background:#11151A;text-align:center}
h1{margin:0 0 10px;font-size:22px}
p{margin:0;color:color-mix(in srgb,#F2F4F7 62%,#0B0D10 38%);line-height:1.5}
</style></head>
<body><div class="card">
<h1>You’re signed in</h1>
<p>You can close this Chrome tab and go back to the PyClips window.</p>
</div></body></html>"""
    return HTMLResponse(html)


def _fail(message: str, ticket: str = "") -> RedirectResponse:
    q = {"auth_error": message}
    if ticket:
        q["ticket"] = ticket
        return RedirectResponse(url=f"/pay?{urlencode(q)}", status_code=302)
    return RedirectResponse(url=f"/login?{urlencode(q)}", status_code=302)


def finish_google(request: Request, code: Optional[str], state: Optional[str], error: Optional[str]):
    ticket = ""
    with _LOCK:
        rec = _PENDING.pop(state, None) if state else None
    if rec:
        ticket = rec.get("ticket") or ""
        if int(rec.get("exp") or 0) < int(time.time()):
            rec = None
    if error:
        return _fail("Google sign-in was cancelled.", ticket)
    if not code or not rec:
        return _fail("Google sign-in expired. Try again.", ticket)
    cfg = load_google_config()
    try:
        tok = requests.post(
            _GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": cfg["google_client_id"],
                "client_secret": cfg["google_client_secret"],
                "redirect_uri": _redirect_uri(cfg),
                "grant_type": "authorization_code",
                "code_verifier": rec["v"],
            },
            timeout=_TIMEOUT,
        )
        tok.raise_for_status()
        access = tok.json().get("access_token")
        if not access:
            raise RuntimeError("no access token")
        info = requests.get(_GOOGLE_USER, headers={"Authorization": f"Bearer {access}"}, timeout=_TIMEOUT)
        info.raise_for_status()
        data = info.json()
        gid = str(data.get("sub") or "").strip()
        email = (data.get("email") or "").strip()
        name = (data.get("name") or data.get("given_name") or "").strip()
    except Exception:
        logger.exception("Google token exchange failed")
        return _fail("Could not finish Google sign-in.", ticket)
    try:
        user = auth.upsert_google_user(gid, email, name)
    except HTTPException as exc:
        return _fail(str(exc.detail), ticket)
    if ticket:
        tickets.bind_ticket(ticket, user["id"])
        rec = tickets.get_ticket(ticket)
        if rec and rec.get("plan") == "login":
            resp = _done_html()
            auth.set_session_cookie(resp, user)
            return resp
    dest = f"/pay?ticket={ticket}" if ticket else "/account"
    resp = RedirectResponse(url=dest, status_code=302)
    auth.set_session_cookie(resp, user)
    return resp
