"""Env + pricing. Keys never ship in the desktop app."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def on_railway() -> bool:
    return bool(
        os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_PROJECT_ID")
        or os.environ.get("RAILWAY_SERVICE_ID")
    )


def _same_filesystem(a: Path, b: Path) -> bool:
    try:
        return a.resolve().stat().st_dev == b.resolve().stat().st_dev
    except OSError:
        return True


def _resolve_data_dir() -> Path:
    env = (os.environ.get("PYCLIPS_DATA_DIR") or "").strip()
    if env:
        return Path(env)
    default = ROOT / "data"
    mounted = Path("/data")
    if on_railway():
        try:
            mounted.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        try:
            if mounted.is_dir() and os.access(str(mounted), os.W_OK):
                return mounted
        except OSError:
            pass
        return default
    try:
        if mounted.is_dir() and os.access(str(mounted), os.W_OK):
            if (mounted / "accounts.db").is_file() or not (default / "accounts.db").is_file():
                return mounted
    except OSError:
        pass
    return default


def is_ephemeral_data_dir(path: Path | None = None) -> bool:
    """True when Railway would throw this directory away on the next deploy."""
    target = path if path is not None else DATA_DIR
    if not on_railway():
        return False
    try:
        resolved = target.resolve()
        app_root = ROOT.resolve()
        if resolved == (ROOT / "data").resolve() or app_root in resolved.parents:
            return True
        if not resolved.exists():
            return True
        probe = Path("/app") if Path("/app").exists() else Path("/")
        return _same_filesystem(resolved, probe)
    except OSError:
        return True


def storage_status() -> dict:
    ephemeral = is_ephemeral_data_dir()
    return {
        "data_dir": str(DATA_DIR),
        "ephemeral": ephemeral,
        "railway": on_railway(),
        "hint": (
            "Mount a Railway volume at /data so unused redeem codes survive deploys."
            if ephemeral
            else ""
        ),
    }


load_dotenv()
DATA_DIR = _resolve_data_dir()

# India — Razorpay INR.
MONTHLY_PAISE = 1900
YEARLY_PAISE = 19900
CURRENCY = "INR"
# USA / outside India — Razorpay International USD (list prices; not FX of ₹19).
MONTHLY_CENTS = 299
YEARLY_CENTS = 2999
CURRENCY_USD = "USD"
MONTHLY_DAYS = 30
YEARLY_DAYS = 365
FREE_VIDEO_CAP = 10


def settings() -> dict:
    load_dotenv()
    public = (os.environ.get("PYCLIPS_PUBLIC_URL") or "https://pyclips.in").rstrip("/")
    return {
        "public_url": public,
        "key_id": (os.environ.get("RAZORPAY_KEY_ID") or "").strip(),
        "key_secret": (os.environ.get("RAZORPAY_KEY_SECRET") or "").strip(),
        "webhook_secret": (os.environ.get("RAZORPAY_WEBHOOK_SECRET") or "").strip(),
        "plan_monthly": (os.environ.get("RAZORPAY_PLAN_MONTHLY") or "").strip(),
        "plan_yearly": (os.environ.get("RAZORPAY_PLAN_YEARLY") or "").strip(),
        # USD plans for Razorpay International (Dashboard → Subscriptions → Plans, currency USD).
        "plan_monthly_usd": (os.environ.get("RAZORPAY_PLAN_MONTHLY_USD") or "").strip(),
        "plan_yearly_usd": (os.environ.get("RAZORPAY_PLAN_YEARLY_USD") or "").strip(),
    }


def _keys_ok(cfg: dict) -> bool:
    kid = cfg["key_id"]
    sec = cfg["key_secret"]
    if not (kid.startswith("rzp_") and sec):
        return False
    if "xxxx" in kid.lower():
        return False
    return True


def razorpay_ready(cfg: dict | None = None) -> bool:
    """True when Razorpay Subscriptions (INR / India) can check out."""
    cfg = cfg if cfg is not None else settings()
    if not _keys_ok(cfg):
        return False
    monthly = cfg["plan_monthly"]
    yearly = cfg["plan_yearly"]
    if not (monthly.startswith("plan_") and yearly.startswith("plan_")):
        return False
    if "xxxx" in monthly.lower() or "xxxx" in yearly.lower():
        return False
    return True


def razorpay_intl_ready(cfg: dict | None = None) -> bool:
    """True when USD Razorpay International subscription plans are configured."""
    cfg = cfg if cfg is not None else settings()
    if not _keys_ok(cfg):
        return False
    monthly = cfg["plan_monthly_usd"]
    yearly = cfg["plan_yearly_usd"]
    if not (monthly.startswith("plan_") and yearly.startswith("plan_")):
        return False
    if "xxxx" in monthly.lower() or "xxxx" in yearly.lower():
        return False
    return True


def payments_ready(cfg: dict | None = None) -> bool:
    """INR and/or USD Razorpay paths are configured."""
    cfg = cfg if cfg is not None else settings()
    return razorpay_ready(cfg) or razorpay_intl_ready(cfg)
