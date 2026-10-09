"""Account website API — auth, Razorpay, desktop claim. No Whisper."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import logging
from typing import Optional

from . import admin, auth, billing, oauth, payouts, tickets
from .config import WEB_DIST, load_dotenv, payments_ready, settings, storage_status

load_dotenv()
logger = logging.getLogger("pyclips.site")

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
    auth.require_password_login()
    user = auth.create_user(body.email, body.password, body.username)
    if body.ticket:
        tickets.bind_ticket(body.ticket, user["id"])
    auth.set_session_cookie(response, user)
    return {"user": user, "subscription": auth.subscription_for(user["id"])}


@app.post("/api/auth/login")
def login(body: auth.LoginBody, response: Response) -> dict:
    auth.require_password_login()
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
    return {
        "google": oauth.google_ready(),
        "microsoft": False,
        "password": auth.password_login_enabled(),
    }


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


@app.get("/api/admin/overview")
def admin_overview(request: Request) -> dict:
    admin.require_admin(request)
    return admin.overview()


@app.get("/api/admin/users")
def admin_list_users(request: Request, q: str = "", plan: str = "all", limit: int = 100, offset: int = 0) -> dict:
    admin.require_admin(request)
    return admin.list_users(q=q, plan=plan, limit=limit, offset=offset)


@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, request: Request, body: admin.UpdateUserBody) -> dict:
    admin.require_admin(request)
    return admin.update_user(user_id, body)


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request) -> dict:
    admin.require_admin(request)
    return admin.delete_user(user_id)


@app.post("/api/admin/download-hits")
def admin_set_download_hits(request: Request, body: admin.SetDownloadHitsBody) -> dict:
    admin.require_admin(request)
    return admin.set_download_hits(body)


@app.get("/api/download")
def public_download() -> dict:
    return admin.public_download()


@app.get("/download")
def download_windows():
    url = admin.windows_exe_target()
    admin.record_download_hit()
    return RedirectResponse(url=url, status_code=302)


@app.get("/api/admin/installer/{platform}")
def admin_get_installer(platform: str, request: Request) -> dict:
    admin.require_admin(request)
    return admin.get_installer(platform)


@app.post("/api/admin/installer/{platform}")
def admin_set_installer(platform: str, request: Request, body: admin.SetDownloadBody) -> dict:
    admin.require_admin(request)
    return admin.set_installer(platform, body)


@app.post("/api/admin/installer/{platform}/clear")
def admin_clear_installer(platform: str, request: Request) -> dict:
    admin.require_admin(request)
    return admin.clear_installer(platform)


@app.get("/download/{platform}")
def download_installer(platform: str):
    return RedirectResponse(url=admin.installer_target(platform), status_code=302)


@app.post("/api/billing/webhook")
async def webhook(request: Request) -> dict:
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature") or ""
    return billing.apply_webhook(raw, sig)


class AffiliateClaim(BaseModel):
    email: str
    order_id: str
    password: str


@app.post("/api/billing/systeme")
async def systeme_sale(request: Request) -> dict:
    """Creator-link sale from systeme.io. Every sale is logged for creator payouts; ₹99 also grants one month Premium."""
    import hmac
    import json as _json

    secret = (billing.settings().get("systeme_secret") or "").strip()
    raw = await request.body()
    signature = request.headers.get("X-Webhook-Signature") or ""
    legacy = request.headers.get("X-PyClips-Affiliate-Secret") or ""
    authorized = False
    if secret and signature:
        authorized = billing.verify_systeme_signature(raw, signature, secret)
    elif secret and legacy:
        authorized = hmac.compare_digest(legacy, secret)
    if not authorized:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    try:
        payload = _json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    email = billing._pick_email(payload)
    order_id = billing._pick_order(payload)
    event = (request.headers.get("X-Webhook-Event") or "").strip().upper()
    if event == "SALE_CANCELED":
        return {"ok": True, "canceled": payouts.mark_systeme_canceled(order_id)}
    if event and event != "SALE_NEW":
        return {"ok": True, "skipped": True, "reason": f"event {event}"}
    monthly = billing.is_affiliate_monthly(payload)
    try:
        payouts.record_systeme_sale(payload, email=email, order_id=order_id, monthly=monthly)
    except Exception:  # noqa: BLE001  (the buyer's Premium must not wait on the ledger)
        logger.exception("Could not record systeme.io sale %s in the payouts ledger", order_id)
    if not monthly:
        return {
            "ok": True,
            "skipped": True,
            "reason": "not_monthly",
            "email": email or None,
            "order_id": order_id or None,
        }
    return billing.grant_affiliate_month(email, order_id)


@app.get("/api/payouts/summary")
def payouts_summary(request: Request) -> dict:
    admin.require_admin(request)
    return {**payouts.summary(), "creators": payouts.list_creators()}


@app.get("/api/payouts/sales")
def payouts_sales(request: Request, month: str = "") -> dict:
    admin.require_admin(request)
    return {"sales": payouts.list_sales(month)}


@app.post("/api/payouts/sales")
def payouts_add_sale(request: Request, body: payouts.SaleBody) -> dict:
    admin.require_admin(request)
    return payouts.add_manual_sale(body)


@app.patch("/api/payouts/sales/{sale_id}")
def payouts_update_sale(sale_id: int, request: Request, body: payouts.SaleUpdateBody) -> dict:
    admin.require_admin(request)
    return payouts.update_sale(sale_id, body)


@app.post("/api/payouts/creators")
def payouts_add_creator(request: Request, body: payouts.CreatorBody) -> dict:
    admin.require_admin(request)
    return payouts.save_creator(body)


@app.patch("/api/payouts/creators/{creator_id}")
def payouts_update_creator(creator_id: int, request: Request, body: payouts.CreatorBody) -> dict:
    admin.require_admin(request)
    return payouts.save_creator(body, creator_id)


@app.delete("/api/payouts/creators/{creator_id}")
def payouts_delete_creator(creator_id: int, request: Request) -> dict:
    admin.require_admin(request)
    return payouts.delete_creator(creator_id)


@app.delete("/api/payouts/sales/{sale_id}")
def payouts_delete_sale(sale_id: int, request: Request) -> dict:
    admin.require_admin(request)
    return payouts.delete_sale(sale_id)


@app.post("/api/payouts/creators/{creator_id}/checked")
def payouts_creator_checked(creator_id: int, request: Request) -> dict:
    admin.require_admin(request)
    return payouts.mark_creator_checked(creator_id)


_JOIN_HITS: dict[str, list[float]] = {}


@app.post("/api/creators/join")
def creator_join(request: Request, body: payouts.JoinBody) -> dict:
    import time

    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (request.client.host if request.client else "?")
    now = time.time()
    hits = [t for t in _JOIN_HITS.get(ip, []) if now - t < 3600]
    if len(hits) >= 10:
        raise HTTPException(status_code=429, detail="Too many tries. Please wait an hour and try again.")
    _JOIN_HITS[ip] = hits + [now]
    return payouts.creator_join(body)


@app.post("/api/payouts/pay-creator")
def payouts_pay_creator(request: Request, body: payouts.CreatorPayBody) -> dict:
    admin.require_admin(request)
    return payouts.pay_creator(body)


@app.post("/api/payouts/pay-partners")
def payouts_pay_partners(request: Request, body: payouts.PartnerPayBody) -> dict:
    admin.require_admin(request)
    return payouts.pay_partners(body)


@app.post("/api/payouts/partners")
def payouts_partner_names(request: Request, body: payouts.PartnersBody) -> dict:
    admin.require_admin(request)
    return payouts.set_partner_names(body)


@app.get("/api/payouts/history")
def payouts_history(request: Request) -> dict:
    admin.require_admin(request)
    return {"payouts": payouts.list_payouts()}


@app.get("/api/payouts/export/{name}.csv")
def payouts_export(name: str, request: Request, start: str = "", end: str = "") -> Response:
    import re

    admin.require_admin(request)
    for value in (start, end):
        if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise HTTPException(status_code=400, detail="Dates must be YYYY-MM-DD.")
    if name == "sales":
        body = payouts.sales_csv(start, end)
    elif name == "payouts":
        body = payouts.payouts_csv(start, end)
    else:
        raise HTTPException(status_code=404, detail="Not found.")
    span = f"-{start or 'start'}-to-{end or 'today'}" if start or end else ""
    return Response(
        content="\ufeff" + body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="pyclips-{name}{span}.csv"'},
    )


@app.post("/api/billing/systeme/claim")
def systeme_claim(body: AffiliateClaim) -> dict:
    return billing.claim_affiliate_password(body.email, body.order_id, body.password)


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


@app.post("/api/desktop/google-id-token")
def desktop_google_id_token(body: oauth.GoogleIdBody) -> dict:
    return oauth.session_from_google_id_token(body.id_token)


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
