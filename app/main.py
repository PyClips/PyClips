"""Account website API — auth, Razorpay, desktop claim. No Whisper."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from typing import Optional

from . import admin, auth, billing, oauth, tickets
from .config import WEB_DIST, load_dotenv, payments_ready, settings, storage_status

load_dotenv()

app = FastAPI(title="PyClips accounts", docs_url=None, redoc_url=None)


class DesktopRefreshBody(BaseModel):
    token: str = Field(default="", max_length=128)
    email: str = Field(default="", max_length=254)


class LicenseBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)


@app.get("/health")
def health() -> dict:
    cfg = settings()
    storage = storage_status()
    from .config import razorpay_intl_ready, razorpay_ready

    return {
        "status": "ok",
        "payments": payments_ready(cfg),
        "razorpay": razorpay_ready(cfg),
        "razorpay_intl": razorpay_intl_ready(cfg),
        "ephemeral": storage["ephemeral"],
    }


@app.post("/api/auth/register")
def register(body: auth.RegisterBody, response: Response) -> dict:
    user = auth.create_user(body.email, body.password, body.username)
    if body.ticket:
        tickets.bind_ticket(body.ticket, user["id"])
    auth.set_session_cookie(response, user)
    return {"user": user, "subscription": auth.subscription_for(user["id"])}


@app.post("/api/auth/login")
def login(body: auth.LoginBody, response: Response) -> dict:
    user = auth.authenticate(body.email, body.password)
    if body.ticket:
        tickets.bind_ticket(body.ticket, user["id"])
    auth.set_session_cookie(response, user)
    return {"user": user, "subscription": auth.subscription_for(user["id"])}


@app.post("/api/auth/logout")
def logout(response: Response) -> dict:
    auth.clear_session(response)
    return {"status": "ok"}


@app.get("/api/auth/providers")
def auth_providers() -> dict:
    return {"google": oauth.google_ready(), "microsoft": False}


@app.get("/api/auth/google")
def auth_google(ticket: str = "", hint: str = ""):
    return oauth.start_google(ticket=ticket, hint=hint)


@app.get("/api/auth/google/callback")
def auth_google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    return oauth.finish_google(request, code, state, error)


@app.get("/api/auth/me")
def me(request: Request) -> dict:
    user = auth.user_from_request(request)
    if not user:
        return {"user": None}
    return {"user": user, "subscription": auth.subscription_for(user["id"])}


@app.get("/api/account/subscription")
def subscription(request: Request) -> dict:
    return auth.subscription_for(auth.current_user(request)["id"], request)


@app.post("/api/billing/subscribe")
def subscribe(request: Request, body: billing.SubscribeBody) -> dict:
    return billing.create_subscription(auth.current_user(request)["id"], body)


@app.get("/api/billing/pricing")
def billing_pricing(request: Request, currency: str = "") -> dict:
    return billing.pricing_for(request, currency)


@app.post("/api/billing/verify")
def verify(request: Request, body: billing.VerifySubBody) -> dict:
    uid = auth.current_user(request)["id"]
    sub = billing.verify_subscription(uid, body)
    return {"status": "ok", "subscription": sub, "user": auth.get_user_by_id(uid)}


@app.post("/api/billing/redeem")
def redeem(request: Request, body: billing.RedeemBody) -> dict:
    uid = auth.current_user(request)["id"]
    sub = billing.redeem_code(uid, body.code)
    return {"status": "ok", "subscription": sub, "user": auth.get_user_by_id(uid)}


@app.post("/api/desktop/redeem")
def desktop_redeem(body: tickets.DesktopRedeemBody) -> dict:
    return tickets.redeem_for_desktop(body)


@app.post("/api/admin/login")
def admin_login(body: admin.AdminLoginBody, response: Response) -> dict:
    return admin.login(body, response)


@app.post("/api/admin/logout")
def admin_logout(response: Response) -> dict:
    admin.clear_admin_cookie(response)
    return {"status": "ok"}


@app.get("/api/admin/coupons")
def admin_list_coupons(request: Request) -> dict:
    admin.require_admin(request)
    return admin.list_coupons()


@app.post("/api/admin/coupons")
def admin_create_coupon(request: Request, body: admin.CreateCouponBody) -> dict:
    admin.require_admin(request)
    return admin.create_coupon(body)


@app.post("/api/admin/coupons/delete")
def admin_delete_coupon(request: Request, body: admin.DeleteCouponBody) -> dict:
    admin.require_admin(request)
    return admin.delete_coupon(body)


@app.get("/api/admin/download")
def admin_get_download(request: Request) -> dict:
    admin.require_admin(request)
    return admin.get_download()


@app.post("/api/admin/download")
def admin_set_download(request: Request, body: admin.SetDownloadBody) -> dict:
    admin.require_admin(request)
    return admin.set_download(body)


@app.post("/api/admin/download/clear")
def admin_clear_download(request: Request) -> dict:
    admin.require_admin(request)
    return admin.clear_download()


@app.get("/api/download")
def public_download() -> dict:
    return admin.public_download()


@app.get("/download")
def download_windows():
    return RedirectResponse(url=admin.windows_exe_target(), status_code=302)


@app.post("/api/billing/webhook")
async def webhook(request: Request) -> dict:
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature") or ""
    return billing.apply_webhook(raw, sig)


@app.post("/api/desktop/begin")
def desktop_begin(body: tickets.BeginBody) -> dict:
    return tickets.begin(body)


@app.get("/api/desktop/peek")
def desktop_peek(ticket: str = "") -> dict:
    return tickets.peek(ticket)


@app.get("/api/desktop/claim")
def desktop_claim(ticket: str = "") -> dict:
    return tickets.claim(ticket)


@app.post("/api/desktop/usage")
def desktop_usage(body: tickets.UsageBody) -> dict:
    return tickets.push_usage(body)


@app.post("/api/desktop/refresh")
def desktop_refresh(body: DesktopRefreshBody) -> dict:
    token = (body.token or "").strip()
    if len(token) >= 8:
        return tickets.refresh_by_token(token)
    raise HTTPException(status_code=401, detail="Desktop sync requires a signed-in desktop link.")


@app.post("/api/desktop/license")
def desktop_license(body: LicenseBody) -> dict:
    # Desktop still posts {email}; subscription sync must use a ticket/token, not email alone.
    _ = body.email
    raise HTTPException(
        status_code=401,
        detail="Desktop sync requires a signed-in desktop link. Sign in with Google from PyClips, or complete checkout from the app, then refresh.",
    )


@app.post("/api/desktop/bind")
def desktop_bind(request: Request, ticket: str = "") -> dict:
    user = auth.current_user(request)
    tickets.bind_ticket(ticket, user["id"])
    return {"status": "ok"}


@app.post("/api/desktop/login-begin")
def desktop_login_begin() -> dict:
    return tickets.begin_login()


@app.get("/api/desktop/login-claim")
def desktop_login_claim(ticket: str = "") -> dict:
    return tickets.login_claim(ticket)


@app.get("/favicon.ico")
def favicon():
    from .config import ROOT

    for p in (
        ROOT / "web" / "dist" / "favicon.ico",
        ROOT / "web" / "public" / "favicon.ico",
        ROOT.parent / "pyclips.ico",
        ROOT.parent / "brand" / "pyclips-icon.png",
    ):
        if p.is_file():
            return FileResponse(p, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="No icon.")


if WEB_DIST.is_dir():
    assets = WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found."}, status_code=404)
        index = WEB_DIST / "index.html"
        if full_path:
            try:
                root = WEB_DIST.resolve()
                target = (WEB_DIST / full_path).resolve()
                target.relative_to(root)
            except (OSError, ValueError):
                return JSONResponse({"detail": "Not found."}, status_code=404)
            if target.is_file():
                return FileResponse(target)
        return FileResponse(index)
