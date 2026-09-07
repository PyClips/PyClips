"""SQLite for website accounts (not the desktop clip DB)."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from pathlib import Path

from .config import DATA_DIR, ROOT, on_railway, storage_status

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "accounts.db"

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
            _init(_conn)
            status = storage_status()
            if status["ephemeral"]:
                logger.warning(
                    "Redeem codes live in %s (ephemeral). Unused codes vanish on the next "
                    "Railway deploy until a volume is mounted at /data.",
                    DATA_DIR,
                )
            else:
                logger.info("Redeem codes persist in %s", DATA_DIR)
        return _conn


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL DEFAULT '',
            username TEXT,
            plan TEXT NOT NULL DEFAULT 'free',
            billing_plan TEXT,
            videos_used INTEGER NOT NULL DEFAULT 0,
            premium_until TEXT,
            rzp_customer_id TEXT,
            rzp_subscription_id TEXT,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            google_id TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            ticket TEXT PRIMARY KEY,
            email TEXT NOT NULL DEFAULT '',
            plan TEXT NOT NULL DEFAULT 'monthly',
            videos_used INTEGER NOT NULL DEFAULT 0,
            user_id INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            sync_token TEXT,
            exp INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            razorpay_payment_id TEXT NOT NULL UNIQUE,
            razorpay_subscription_id TEXT NOT NULL DEFAULT '',
            amount_paise INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'subscription',
            provider TEXT NOT NULL DEFAULT 'razorpay',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS coupon_redemptions (
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, code)
        );
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY,
            spec_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "google_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
    if "stripe_customer_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    if "stripe_subscription_id" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
    pay_cols = {row[1] for row in conn.execute("PRAGMA table_info(payments)").fetchall()}
    if "provider" not in pay_cols:
        conn.execute("ALTER TABLE payments ADD COLUMN provider TEXT NOT NULL DEFAULT 'razorpay'")
    red_cols = {row[1] for row in conn.execute("PRAGMA table_info(coupon_redemptions)").fetchall()}
    if "days" not in red_cols:
        conn.execute("ALTER TABLE coupon_redemptions ADD COLUMN days INTEGER")
    conn.commit()
    from . import auth as auth_mod

    auth_mod.merge_duplicate_emails(conn)
    _migrate_coupons(conn)


def secret_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "session.secret"


def _coupon_stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_coupon_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _coupons_from_table(conn: sqlite3.Connection) -> dict:
    out = {}
    for row in conn.execute("SELECT code, spec_json FROM coupons"):
        try:
            spec = json.loads(row["spec_json"])
        except (TypeError, ValueError):
            continue
        out[str(row["code"])] = spec
    return out


def _coupon_import_paths() -> list[Path]:
    paths = [
        ROOT / "data" / "coupons.example.json",
        ROOT / "data" / "coupons.json",
        DATA_DIR / "coupons.json",
    ]
    if on_railway():
        paths[2:2] = [Path("/app/data") / "coupons.json", Path("/data") / "coupons.json"]
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _coupon_mirror_paths() -> list[Path]:
    paths = [DATA_DIR / "coupons.json"]
    if not on_railway():
        return paths
    for extra in (Path("/data") / "coupons.json", Path("/app/data") / "coupons.json"):
        try:
            if extra.resolve() == paths[0].resolve():
                continue
        except OSError:
            pass
        parent = extra.parent
        try:
            if parent.is_dir() and os.access(str(parent), os.W_OK):
                paths.append(extra)
        except OSError:
            continue
    return paths


def _write_coupon_json(data: dict) -> None:
    """Best-effort mirror. SQLite is the source of truth so admin codes survive JSON resets."""
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    for path in _coupon_mirror_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(str(tmp), str(path))
        except OSError:
            logger.warning("Could not mirror redeem catalog to %s", path)


def _upsert_coupon_rows(conn: sqlite3.Connection, data: dict, *, drop_missing: bool) -> None:
    stamp = _coupon_stamp()
    keep = set()
    for code, spec in data.items():
        key = str(code).strip()
        if not key:
            continue
        keep.add(key)
        conn.execute(
            """INSERT INTO coupons (code, spec_json, created_at) VALUES (?, ?, ?)
               ON CONFLICT(code) DO UPDATE SET spec_json = excluded.spec_json""",
            (key, json.dumps(spec, ensure_ascii=False), stamp),
        )
    if drop_missing:
        for row in conn.execute("SELECT code FROM coupons").fetchall():
            if str(row["code"]) not in keep:
                conn.execute("DELETE FROM coupons WHERE code = ?", (row["code"],))


def _migrate_coupons(conn: sqlite3.Connection) -> None:
    existing = _coupons_from_table(conn)
    incoming = {}
    for path in _coupon_import_paths():
        incoming.update(_read_coupon_json(path))
    known = {str(k).upper() for k in list(incoming) + list(existing)}
    for row in conn.execute("SELECT DISTINCT code FROM coupon_redemptions"):
        code = str(row["code"] or "").strip()
        if not code or code.upper() in known:
            continue
        incoming[code] = {"days": 30, "months": 1, "restored": True}
        known.add(code.upper())
    merged = dict(incoming)
    merged.update(existing)
    if not merged or merged == existing:
        return
    _upsert_coupon_rows(conn, merged, drop_missing=False)
    conn.commit()
    logger.info("Redeem catalog has %s code(s)", len(merged))
    try:
        _write_coupon_json(merged)
    except OSError:
        pass


def load_coupons() -> dict:
    conn = get_conn()
    data = _coupons_from_table(conn)
    if data:
        return data
    return _read_coupon_json(DATA_DIR / "coupons.json")


def save_coupons(data: dict) -> None:
    if not isinstance(data, dict):
        raise TypeError("coupons must be an object")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        conn = get_conn()
        _upsert_coupon_rows(conn, data, drop_missing=True)
        conn.commit()
        try:
            _write_coupon_json(data)
        except OSError:
            pass


WINDOWS_EXE_KEY = "windows_exe_url"


def get_setting(key: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT value, updated_at FROM site_settings WHERE key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    return {"value": str(row["value"] or ""), "updated_at": str(row["updated_at"] or "")}


def set_setting(key: str, value: str) -> dict:
    stamp = _coupon_stamp()
    with _lock:
        conn = get_conn()
        conn.execute(
            """INSERT INTO site_settings (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, value, stamp),
        )
        conn.commit()
    return {"value": value, "updated_at": stamp}


def delete_setting(key: str) -> None:
    with _lock:
        conn = get_conn()
        conn.execute("DELETE FROM site_settings WHERE key = ?", (key,))
        conn.commit()
