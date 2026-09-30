"""Creator-link sales ledger and payouts.

Every systeme.io sale (₹99 monthly and ₹599 lifetime, renewals included) is recorded here.
Split of the full sale price: creator 40%, then the two partners 30% each.
Creators are paid weekly (Monday–Sunday, India time); partners monthly.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException
from pydantic import BaseModel, Field

from . import db

IST = timezone(timedelta(hours=5, minutes=30))
CREATOR_PCT = 40
PARTNERS_KEY = "payout_partner_names"
DEFAULT_PARTNERS = ("You", "Partner")
# systeme.io may reuse one order id for each monthly charge; a repeat this long after the
# first is a renewal, a repeat sooner is a webhook retry.
RENEWAL_GAP = timedelta(days=20)
_CODE = re.compile(r"^[A-Za-z0-9_-]{2,80}$")


class CreatorBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(default="", max_length=254)
    affiliate_code: str = Field(default="", max_length=80)
    pay_to: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=500)
    active: bool = True


class JoinBody(BaseModel):
    affiliate_code: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(default="", max_length=254)
    pay_to: str = Field(min_length=3, max_length=200)


class SaleBody(BaseModel):
    buyer_email: str = Field(default="", max_length=254)
    plan: str = Field(default="monthly", max_length=16)
    amount_rupees: float = Field(ge=0, le=100_000)
    creator_id: Optional[int] = None
    sold_on: str = Field(default="", max_length=10)
    order_id: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=500)


class SaleUpdateBody(BaseModel):
    creator_id: Optional[int] = None
    clear_creator: bool = False
    amount_rupees: Optional[float] = Field(default=None, ge=0, le=100_000)
    refunded: Optional[bool] = None
    note: Optional[str] = Field(default=None, max_length=500)
    reviewed: Optional[bool] = None


class CreatorPayBody(BaseModel):
    creator_id: int
    week_start: str = Field(min_length=10, max_length=10)
    reference: str = Field(default="", max_length=200)


class PartnerPayBody(BaseModel):
    month: str = Field(min_length=7, max_length=7)
    reference: str = Field(default="", max_length=200)


class PartnersBody(BaseModel):
    first: str = Field(min_length=1, max_length=40)
    second: str = Field(min_length=1, max_length=40)


# --------------------------------------------------------------------------- storage
def ensure_tables(conn=None) -> None:
    conn = conn or db.get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS creators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            affiliate_code TEXT NOT NULL DEFAULT '',
            pay_to TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_key TEXT NOT NULL UNIQUE,
            order_id TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'systeme',
            buyer_email TEXT NOT NULL DEFAULT '',
            plan TEXT NOT NULL DEFAULT 'monthly',
            amount_paise INTEGER NOT NULL,
            creator_id INTEGER,
            matched_by TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            sold_at TEXT NOT NULL,
            refunded INTEGER NOT NULL DEFAULT 0,
            canceled_at TEXT,
            reviewed INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            creator_payout_id INTEGER,
            creator_clawback_id INTEGER,
            partner_payout_id INTEGER,
            partner_clawback_id INTEGER,
            raw_json TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sales_order ON sales(order_id);
        CREATE INDEX IF NOT EXISTS idx_sales_buyer ON sales(buyer_email);
        CREATE TABLE IF NOT EXISTS payouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            creator_id INTEGER,
            period TEXT NOT NULL,
            amount_paise INTEGER NOT NULL,
            first_paise INTEGER NOT NULL DEFAULT 0,
            second_paise INTEGER NOT NULL DEFAULT 0,
            sale_count INTEGER NOT NULL DEFAULT 0,
            reference TEXT NOT NULL DEFAULT '',
            paid_at TEXT NOT NULL
        );
        """
    )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(creators)").fetchall()}
    if "needs_check" not in cols:
        conn.execute("ALTER TABLE creators ADD COLUMN needs_check INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def _conn():
    conn = db.get_conn()
    ensure_tables(conn)
    return conn


def _stamp(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def split(amount_paise: int, has_creator: bool = True) -> tuple[int, int, int]:
    """(creator, first partner, second partner) in paise. Always sums to the sale amount."""
    amount = max(0, int(amount_paise))
    creator = amount * CREATOR_PCT // 100 if has_creator else 0
    rest = amount - creator
    first = (rest + 1) // 2
    return creator, first, rest - first


def week_start(dt: datetime) -> str:
    local = dt.astimezone(IST).date()
    return (local - timedelta(days=local.weekday())).isoformat()


def month_of(dt: datetime) -> str:
    return dt.astimezone(IST).strftime("%Y-%m")


def partner_names() -> tuple[str, str]:
    row = db.get_setting(PARTNERS_KEY)
    if row:
        try:
            names = json.loads(row["value"])
            if isinstance(names, list) and len(names) == 2 and all(names):
                return str(names[0]), str(names[1])
        except ValueError:
            pass
    return DEFAULT_PARTNERS


def set_partner_names(body: PartnersBody) -> dict:
    db.set_setting(PARTNERS_KEY, json.dumps([body.first.strip(), body.second.strip()]))
    return {"partners": list(partner_names())}


# --------------------------------------------------------------------------- systeme.io intake
def _affiliate_codes(payload: dict) -> list[str]:
    """Affiliate codes a systeme.io sale carries: sa= in the buyer's source URL, or any affiliate field."""
    found: list[str] = []
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    nested = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    for url in (customer.get("sourceUrl"), customer.get("source_url"), nested.get("sourceUrl"), nested.get("source_url")):
        if isinstance(url, str) and url:
            query = parse_qs(urlparse(url.replace("\\/", "/")).query)
            for key in ("sa", "aff", "affiliate", "ref"):
                found.extend(v.strip() for v in query.get(key, []) if v.strip())

    def walk(node, depth=0):
        if depth > 4:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if "affiliate" in str(key).lower():
                    if isinstance(value, (str, int)) and str(value).strip():
                        found.append(str(value).strip())
                    elif isinstance(value, dict):
                        for sub in ("code", "id", "email", "affiliateCode"):
                            if value.get(sub):
                                found.append(str(value[sub]).strip())
                walk(value, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, depth + 1)

    walk(payload)
    return [c for c in dict.fromkeys(found) if c]


def _source_url(payload: dict) -> str:
    for holder in (payload.get("customer"), (payload.get("data") or {}).get("customer") if isinstance(payload.get("data"), dict) else None):
        if isinstance(holder, dict):
            url = holder.get("sourceUrl") or holder.get("source_url")
            if isinstance(url, str):
                return url.replace("\\/", "/")[:500]
    return ""


def _to_paise(value) -> int:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0
    if n <= 0:
        return 0
    # systeme.io may send rupees (99) or paise (9900); PyClips never sells below ₹1,000 in paise terms.
    return int(round(n * 100)) if n < 1000 else int(round(n))


def _sale_amount(payload: dict, plan: str) -> int:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    order = payload.get("order") if isinstance(payload.get("order"), dict) else data.get("order") or {}
    price = payload.get("pricePlan") if isinstance(payload.get("pricePlan"), dict) else data.get("pricePlan") or {}
    for value in (order.get("totalPrice") if isinstance(order, dict) else None, price.get("amount") if isinstance(price, dict) else None):
        paise = _to_paise(value)
        if paise:
            return paise
    return 59900 if plan == "lifetime" else 9900


def _sold_at(payload: dict) -> datetime:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    for holder in (payload.get("orderItem"), payload.get("order"), data.get("orderItem"), data.get("order")):
        if isinstance(holder, dict) and holder.get("createdAt"):
            try:
                return datetime.fromisoformat(str(holder["createdAt"]).replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                pass
    return datetime.now(timezone.utc)


def _creator_for_codes(conn, codes: list[str]) -> Optional[int]:
    for code in codes:
        row = conn.execute(
            "SELECT id FROM creators WHERE affiliate_code != '' AND lower(affiliate_code) = lower(?)",
            (code,),
        ).fetchone()
        if row:
            return int(row["id"])
        row = conn.execute(
            "SELECT id FROM creators WHERE email != '' AND lower(email) = lower(?)",
            (code,),
        ).fetchone()
        if row:
            return int(row["id"])
    return None


def _earlier_creator(conn, buyer_email: str) -> Optional[int]:
    if not buyer_email:
        return None
    row = conn.execute(
        "SELECT creator_id FROM sales WHERE lower(buyer_email) = lower(?) AND creator_id IS NOT NULL "
        "ORDER BY sold_at DESC LIMIT 1",
        (buyer_email,),
    ).fetchone()
    return int(row["creator_id"]) if row else None


def record_systeme_sale(payload: dict, *, email: str, order_id: str, monthly: bool) -> dict:
    """Store one systeme.io sale. Safe to call again for a webhook retry."""
    conn = _conn()
    plan = "monthly" if monthly else "lifetime"
    sold = _sold_at(payload)
    now = datetime.now(timezone.utc)
    order_id = (order_id or "").strip()[:80]
    key = f"systeme:{order_id}" if order_id else f"systeme:{email}:{_stamp(sold)}"
    prior = conn.execute(
        "SELECT id, sold_at FROM sales WHERE order_id = ? AND source = 'systeme' ORDER BY sold_at DESC LIMIT 1",
        (order_id,),
    ).fetchone() if order_id else conn.execute("SELECT id, sold_at FROM sales WHERE sale_key = ?", (key,)).fetchone()
    if prior:
        if now - _parse(prior["sold_at"]) < RENEWAL_GAP:
            return {"recorded": False, "duplicate": True, "sale_id": int(prior["id"])}
        count = conn.execute("SELECT COUNT(*) AS n FROM sales WHERE order_id = ?", (order_id,)).fetchone()["n"]
        key = f"{key}#{int(count) + 1}"
        sold = now
    codes = _affiliate_codes(payload)
    creator_id = _creator_for_codes(conn, codes)
    matched = "affiliate code" if creator_id else ""
    if creator_id is None:
        creator_id = _earlier_creator(conn, email)
        matched = "earlier sale" if creator_id else ""
    cur = conn.execute(
        """INSERT INTO sales (sale_key, order_id, source, buyer_email, plan, amount_paise, creator_id, matched_by,
               source_url, sold_at, note, raw_json, created_at)
           VALUES (?, ?, 'systeme', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            key,
            order_id,
            (email or "").strip().lower(),
            plan,
            _sale_amount(payload, plan),
            creator_id,
            matched,
            _source_url(payload),
            _stamp(sold),
            "" if creator_id or not codes else f"Affiliate code {', '.join(codes)} matches no creator",
            json.dumps(payload, ensure_ascii=False)[:20000],
            _stamp(now),
        ),
    )
    conn.commit()
    return {"recorded": True, "sale_id": int(cur.lastrowid), "creator_id": creator_id}


def mark_systeme_canceled(order_id: str) -> dict:
    conn = _conn()
    order_id = (order_id or "").strip()
    if not order_id:
        return {"updated": 0}
    cur = conn.execute(
        "UPDATE sales SET canceled_at = ?, reviewed = 0 WHERE order_id = ? AND canceled_at IS NULL",
        (_stamp(), order_id),
    )
    conn.commit()
    return {"updated": cur.rowcount}


# --------------------------------------------------------------------------- creators
def _creator_dict(row) -> dict:
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "email": row["email"],
        "affiliate_code": row["affiliate_code"],
        "pay_to": row["pay_to"],
        "note": row["note"],
        "active": bool(row["active"]),
        "needs_check": bool(row["needs_check"]),
    }


def list_creators() -> list[dict]:
    return [_creator_dict(r) for r in _conn().execute("SELECT * FROM creators ORDER BY active DESC, name")]


def _clean_code(code: str) -> str:
    code = (code or "").strip()
    if code and not _CODE.match(code):
        raise HTTPException(status_code=400, detail="Affiliate code: letters, numbers, - and _ only (the part after sa=).")
    return code


def save_creator(body: CreatorBody, creator_id: Optional[int] = None) -> dict:
    conn = _conn()
    code = _clean_code(body.affiliate_code)
    if code:
        clash = conn.execute(
            "SELECT id FROM creators WHERE lower(affiliate_code) = lower(?) AND id != ?",
            (code, creator_id or 0),
        ).fetchone()
        if clash:
            raise HTTPException(status_code=400, detail="Another creator already has that affiliate code.")
    values = (body.name.strip(), body.email.strip().lower(), code, body.pay_to.strip(), body.note.strip(), int(body.active))
    if creator_id:
        cur = conn.execute(
            "UPDATE creators SET name = ?, email = ?, affiliate_code = ?, pay_to = ?, note = ?, active = ?, needs_check = 0 WHERE id = ?",
            values + (creator_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Creator not found.")
    else:
        cur = conn.execute(
            "INSERT INTO creators (name, email, affiliate_code, pay_to, note, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            values + (_stamp(),),
        )
        creator_id = int(cur.lastrowid)
    conn.commit()
    if code:
        _rematch_unassigned(conn)
    return _creator_dict(conn.execute("SELECT * FROM creators WHERE id = ?", (creator_id,)).fetchone())


def _rematch_unassigned(conn) -> int:
    """After a creator gets a code, pick up earlier sales that carried it."""
    fixed = 0
    for row in conn.execute("SELECT id, raw_json FROM sales WHERE creator_id IS NULL AND raw_json != ''").fetchall():
        try:
            payload = json.loads(row["raw_json"])
        except ValueError:
            continue
        creator_id = _creator_for_codes(conn, _affiliate_codes(payload)) if isinstance(payload, dict) else None
        if creator_id:
            conn.execute(
                "UPDATE sales SET creator_id = ?, matched_by = 'affiliate code', note = '' WHERE id = ?",
                (creator_id, row["id"]),
            )
            fixed += 1
    conn.commit()
    return fixed


def creator_join(body: JoinBody) -> dict:
    """A creator registers from the link in their systeme.io affiliate email (sa= filled in by systeme.io).

    Public, so it never overwrites an existing payout destination; the owner confirms each join.
    """
    conn = _conn()
    code = _clean_code(body.affiliate_code)
    if not code:
        raise HTTPException(status_code=400, detail="This link is missing your affiliate code. Use the link from your systeme.io email.")
    name, email, pay_to = body.name.strip(), body.email.strip().lower(), body.pay_to.strip()
    row = conn.execute("SELECT * FROM creators WHERE lower(affiliate_code) = lower(?)", (code,)).fetchone()
    if row is None and email:
        row = conn.execute(
            "SELECT * FROM creators WHERE affiliate_code = '' AND email != '' AND lower(email) = ?", (email,)
        ).fetchone()
    if row is not None and row["pay_to"]:
        raise HTTPException(
            status_code=409,
            detail="You're already registered. To change your payout details, email pyclips.in@gmail.com.",
        )
    if row is not None:
        conn.execute(
            "UPDATE creators SET name = CASE WHEN name = '' THEN ? ELSE name END, "
            "email = CASE WHEN email = '' THEN ? ELSE email END, affiliate_code = ?, pay_to = ?, needs_check = 1 WHERE id = ?",
            (name, email, code, pay_to, row["id"]),
        )
        creator_id = int(row["id"])
    else:
        cur = conn.execute(
            "INSERT INTO creators (name, email, affiliate_code, pay_to, note, active, created_at, needs_check) "
            "VALUES (?, ?, ?, ?, 'Joined from the systeme.io link', 1, ?, 1)",
            (name, email, code, pay_to, _stamp()),
        )
        creator_id = int(cur.lastrowid)
    conn.commit()
    _rematch_unassigned(conn)
    return {"ok": True, "name": name, "creator_id": creator_id}


def delete_creator(creator_id: int) -> dict:
    """Remove a creator (test entries, mistakes). Their unpaid sales go back to "Needs your attention"."""
    conn = _conn()
    if conn.execute("SELECT 1 FROM creators WHERE id = ?", (creator_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Creator not found.")
    if conn.execute("SELECT 1 FROM payouts WHERE creator_id = ?", (creator_id,)).fetchone():
        raise HTTPException(status_code=400, detail="This creator has payouts on record; mark them stopped instead of deleting.")
    moved = conn.execute(
        "UPDATE sales SET creator_id = NULL, matched_by = '', reviewed = 0 WHERE creator_id = ?", (creator_id,)
    ).rowcount
    conn.execute("DELETE FROM creators WHERE id = ?", (creator_id,))
    conn.commit()
    return {"ok": True, "sales_unassigned": moved}


def delete_sale(sale_id: int) -> dict:
    conn = _conn()
    row = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Sale not found.")
    if row["creator_payout_id"] or row["partner_payout_id"]:
        raise HTTPException(status_code=400, detail="This sale is already in a payout; mark it Refunded instead.")
    conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    conn.commit()
    return {"ok": True}


def mark_creator_checked(creator_id: int) -> dict:
    conn = _conn()
    cur = conn.execute("UPDATE creators SET needs_check = 0 WHERE id = ?", (creator_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Creator not found.")
    return {"ok": True}


# --------------------------------------------------------------------------- sales
def _creator_exists(conn, creator_id: Optional[int]) -> None:
    if creator_id and not conn.execute("SELECT 1 FROM creators WHERE id = ?", (creator_id,)).fetchone():
        raise HTTPException(status_code=400, detail="Unknown creator.")


def add_manual_sale(body: SaleBody) -> dict:
    conn = _conn()
    plan = body.plan if body.plan in ("monthly", "lifetime") else "monthly"
    _creator_exists(conn, body.creator_id)
    if body.sold_on:
        try:
            day = datetime.strptime(body.sold_on, "%Y-%m-%d").replace(hour=12, tzinfo=IST)
        except ValueError:
            raise HTTPException(status_code=400, detail="Date must be YYYY-MM-DD.")
    else:
        day = datetime.now(timezone.utc)
    now = _stamp()
    order_id = body.order_id.strip()
    key = f"manual:{order_id}" if order_id else f"manual:{now}:{body.buyer_email.strip().lower()}"
    try:
        cur = conn.execute(
            """INSERT INTO sales (sale_key, order_id, source, buyer_email, plan, amount_paise, creator_id, matched_by,
                   sold_at, note, reviewed, created_at)
               VALUES (?, ?, 'manual', ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                key,
                order_id,
                body.buyer_email.strip().lower(),
                plan,
                int(round(body.amount_rupees * 100)),
                body.creator_id,
                "added by hand" if body.creator_id else "",
                _stamp(day),
                body.note.strip(),
                now,
            ),
        )
    except Exception as exc:  # sqlite3.IntegrityError on a repeated order id
        conn.rollback()
        raise HTTPException(status_code=400, detail="A sale with that order number is already recorded.") from exc
    conn.commit()
    return {"id": int(cur.lastrowid)}


def update_sale(sale_id: int, body: SaleUpdateBody) -> dict:
    conn = _conn()
    row = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sale not found.")
    paid = row["creator_payout_id"] or row["partner_payout_id"]
    if body.clear_creator or body.creator_id is not None:
        if row["creator_payout_id"]:
            raise HTTPException(status_code=400, detail="This sale's creator is already paid; it can't move to another creator.")
        _creator_exists(conn, body.creator_id)
        new = None if body.clear_creator else body.creator_id
        conn.execute(
            "UPDATE sales SET creator_id = ?, matched_by = ?, note = CASE WHEN ? IS NULL THEN note ELSE '' END WHERE id = ?",
            (new, "set by hand" if new else "", new, sale_id),
        )
    if body.amount_rupees is not None:
        if paid:
            raise HTTPException(status_code=400, detail="This sale is already in a payout; its amount can't change.")
        conn.execute("UPDATE sales SET amount_paise = ? WHERE id = ?", (int(round(body.amount_rupees * 100)), sale_id))
    if body.refunded is not None:
        conn.execute("UPDATE sales SET refunded = ?, reviewed = 1 WHERE id = ?", (int(body.refunded), sale_id))
    if body.note is not None:
        conn.execute("UPDATE sales SET note = ? WHERE id = ?", (body.note.strip(), sale_id))
    if body.reviewed is not None:
        conn.execute("UPDATE sales SET reviewed = ? WHERE id = ?", (int(body.reviewed), sale_id))
    conn.commit()
    return _sale_dict(conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone(), _creator_names(conn))


def _creator_names(conn) -> dict[int, str]:
    return {int(r["id"]): r["name"] for r in conn.execute("SELECT id, name FROM creators")}


def _sale_dict(row, names: dict[int, str]) -> dict:
    sold = _parse(row["sold_at"])
    has_creator = row["creator_id"] is not None
    creator, first, second = split(row["amount_paise"], has_creator)
    return {
        "id": int(row["id"]),
        "order_id": row["order_id"],
        "source": row["source"],
        "buyer_email": row["buyer_email"],
        "plan": row["plan"],
        "amount_paise": int(row["amount_paise"]),
        "creator_id": row["creator_id"],
        "creator_name": names.get(int(row["creator_id"])) if has_creator else None,
        "matched_by": row["matched_by"],
        "source_url": row["source_url"],
        "sold_at": row["sold_at"],
        "sold_day": sold.astimezone(IST).date().isoformat(),
        "week_start": week_start(sold),
        "month": month_of(sold),
        "refunded": bool(row["refunded"]),
        "canceled_at": row["canceled_at"],
        "reviewed": bool(row["reviewed"]),
        "note": row["note"],
        "creator_paise": creator,
        "first_paise": first,
        "second_paise": second,
        "creator_paid": bool(row["creator_payout_id"]),
        "partners_paid": bool(row["partner_payout_id"]),
    }


def list_sales(month: str = "") -> list[dict]:
    conn = _conn()
    names = _creator_names(conn)
    rows = conn.execute("SELECT * FROM sales ORDER BY sold_at DESC, id DESC").fetchall()
    out = [_sale_dict(r, names) for r in rows]
    return [s for s in out if s["month"] == month] if month else out


# --------------------------------------------------------------------------- what is owed
def _creator_due(conn) -> list[dict]:
    """Unpaid creator money grouped by creator and week, including refunds to take back."""
    names = _creator_names(conn)
    groups: dict[tuple[int, str], dict] = {}
    for row in conn.execute("SELECT * FROM sales WHERE creator_id IS NOT NULL").fetchall():
        share = split(row["amount_paise"])[0]
        earn = not row["refunded"] and not row["creator_payout_id"]
        takeback = row["refunded"] and row["creator_payout_id"] and not row["creator_clawback_id"]
        if not (earn or takeback):
            continue
        week = week_start(_parse(row["sold_at"]))
        g = groups.setdefault(
            (int(row["creator_id"]), week),
            {"creator_id": int(row["creator_id"]), "creator_name": names.get(int(row["creator_id"]), "?"),
             "week_start": week, "sales": 0, "earned_paise": 0, "takeback_paise": 0},
        )
        if earn:
            g["sales"] += 1
            g["earned_paise"] += share
        else:
            g["takeback_paise"] += share
    today = datetime.now(IST).date()
    out = []
    for g in groups.values():
        start = datetime.strptime(g["week_start"], "%Y-%m-%d").date()
        g["week_end"] = (start + timedelta(days=6)).isoformat()
        g["amount_paise"] = g["earned_paise"] - g["takeback_paise"]
        g["status"] = "due" if start + timedelta(days=6) < today else "this week"
        out.append(g)
    return sorted(out, key=lambda g: (g["week_start"], g["creator_name"]))


def _partner_due(conn) -> list[dict]:
    groups: dict[str, dict] = {}
    for row in conn.execute("SELECT * FROM sales WHERE creator_id IS NOT NULL").fetchall():
        _creator, first, second = split(row["amount_paise"])
        earn = not row["refunded"] and not row["partner_payout_id"]
        takeback = row["refunded"] and row["partner_payout_id"] and not row["partner_clawback_id"]
        if not (earn or takeback):
            continue
        month = month_of(_parse(row["sold_at"]))
        g = groups.setdefault(month, {"month": month, "sales": 0, "gross_paise": 0, "creator_paise": 0, "rest_paise": 0})
        sign = 1 if earn else -1
        if earn:
            g["sales"] += 1
            g["gross_paise"] += int(row["amount_paise"])
            g["creator_paise"] += _creator
        g["rest_paise"] += sign * (first + second)
    current = datetime.now(IST).strftime("%Y-%m")
    for g in groups.values():
        rest = g.pop("rest_paise")
        g["first_paise"] = rest - rest // 2
        g["second_paise"] = rest // 2
        g["status"] = "due" if g["month"] < current else "this month"
    return sorted(groups.values(), key=lambda g: g["month"])


def summary() -> dict:
    conn = _conn()
    names = _creator_names(conn)
    creator_due = _creator_due(conn)
    partner_due = _partner_due(conn)
    attention = []
    for row in conn.execute("SELECT * FROM sales ORDER BY sold_at DESC").fetchall():
        s = _sale_dict(row, names)
        if s["creator_id"] is None and not s["reviewed"]:
            attention.append({**s, "problem": "No creator matched. Pick the creator, or mark it as a direct sale."})
        elif s["canceled_at"] and not s["reviewed"]:
            attention.append({**s, "problem": "Canceled in systeme.io. If the buyer got a refund, mark it Refunded."})
    now = datetime.now(IST)
    this_week = week_start(now)
    this_month = now.strftime("%Y-%m")
    all_sales = [_sale_dict(r, names) for r in conn.execute("SELECT * FROM sales WHERE refunded = 0 AND creator_id IS NOT NULL")]
    first, second = partner_names()
    return {
        "partners": [first, second],
        "creator_pct": CREATOR_PCT,
        "owed_creators_paise": sum(g["amount_paise"] for g in creator_due if g["status"] == "due"),
        "building_creators_paise": sum(g["amount_paise"] for g in creator_due if g["status"] != "due"),
        "owed_partners_paise": sum(g["first_paise"] + g["second_paise"] for g in partner_due if g["status"] == "due"),
        "week_sales": sum(1 for s in all_sales if s["week_start"] == this_week),
        "month_sales": sum(1 for s in all_sales if s["month"] == this_month),
        "month_gross_paise": sum(s["amount_paise"] for s in all_sales if s["month"] == this_month),
        "creator_due": creator_due,
        "partner_due": partner_due,
        "attention": attention,
        "new_creators": [_creator_dict(r) for r in conn.execute("SELECT * FROM creators WHERE needs_check = 1 ORDER BY created_at")],
    }


# --------------------------------------------------------------------------- mark paid
def pay_creator(body: CreatorPayBody) -> dict:
    conn = _conn()
    try:
        start = datetime.strptime(body.week_start, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Bad week.")
    group = next(
        (g for g in _creator_due(conn) if g["creator_id"] == body.creator_id and g["week_start"] == start.isoformat()),
        None,
    )
    if not group:
        raise HTTPException(status_code=400, detail="Nothing unpaid for that creator that week.")
    cur = conn.execute(
        "INSERT INTO payouts (kind, creator_id, period, amount_paise, sale_count, reference, paid_at) VALUES ('creator', ?, ?, ?, ?, ?, ?)",
        (body.creator_id, group["week_start"], group["amount_paise"], group["sales"], body.reference.strip(), _stamp()),
    )
    payout_id = int(cur.lastrowid)
    for row in conn.execute("SELECT * FROM sales WHERE creator_id = ?", (body.creator_id,)).fetchall():
        if week_start(_parse(row["sold_at"])) != group["week_start"]:
            continue
        if not row["refunded"] and not row["creator_payout_id"]:
            conn.execute("UPDATE sales SET creator_payout_id = ? WHERE id = ?", (payout_id, row["id"]))
        elif row["refunded"] and row["creator_payout_id"] and not row["creator_clawback_id"]:
            conn.execute("UPDATE sales SET creator_clawback_id = ? WHERE id = ?", (payout_id, row["id"]))
    conn.commit()
    return {"payout_id": payout_id, "amount_paise": group["amount_paise"]}


def pay_partners(body: PartnerPayBody) -> dict:
    conn = _conn()
    group = next((g for g in _partner_due(conn) if g["month"] == body.month), None)
    if not group:
        raise HTTPException(status_code=400, detail="Nothing unpaid for that month.")
    total = group["first_paise"] + group["second_paise"]
    cur = conn.execute(
        """INSERT INTO payouts (kind, period, amount_paise, first_paise, second_paise, sale_count, reference, paid_at)
           VALUES ('partner', ?, ?, ?, ?, ?, ?, ?)""",
        (body.month, total, group["first_paise"], group["second_paise"], group["sales"], body.reference.strip(), _stamp()),
    )
    payout_id = int(cur.lastrowid)
    for row in conn.execute("SELECT * FROM sales WHERE creator_id IS NOT NULL").fetchall():
        if month_of(_parse(row["sold_at"])) != body.month:
            continue
        if not row["refunded"] and not row["partner_payout_id"]:
            conn.execute("UPDATE sales SET partner_payout_id = ? WHERE id = ?", (payout_id, row["id"]))
        elif row["refunded"] and row["partner_payout_id"] and not row["partner_clawback_id"]:
            conn.execute("UPDATE sales SET partner_clawback_id = ? WHERE id = ?", (payout_id, row["id"]))
    conn.commit()
    return {"payout_id": payout_id, "amount_paise": total}


def list_payouts() -> list[dict]:
    conn = _conn()
    names = _creator_names(conn)
    out = []
    for row in conn.execute("SELECT * FROM payouts ORDER BY paid_at DESC, id DESC"):
        out.append({
            "id": int(row["id"]),
            "kind": row["kind"],
            "creator_name": names.get(int(row["creator_id"])) if row["creator_id"] else None,
            "period": row["period"],
            "amount_paise": int(row["amount_paise"]),
            "first_paise": int(row["first_paise"]),
            "second_paise": int(row["second_paise"]),
            "sale_count": int(row["sale_count"]),
            "reference": row["reference"],
            "paid_at": row["paid_at"],
        })
    return out


# --------------------------------------------------------------------------- CSV
def _rupees(paise: int) -> str:
    return f"{paise / 100:.2f}"


def _in_range(day: str, start: str, end: str) -> bool:
    """Inclusive YYYY-MM-DD bounds (India dates); an empty bound is open."""
    return (not start or day >= start) and (not end or day <= end)


def _ist_day(stamp: str) -> str:
    return _parse(stamp).astimezone(IST).date().isoformat()


def sales_csv(start: str = "", end: str = "") -> str:
    first, second = partner_names()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date (IST)", "Order", "Source", "Buyer", "Plan", "Amount ₹", "Creator", "Creator 40% ₹",
                f"{first} 50% of rest ₹", f"{second} 50% of rest ₹", "Refunded", "Creator paid", "Partners paid", "Note"])
    totals = [0, 0, 0, 0]
    count = 0
    for s in list_sales():
        if not _in_range(s["sold_day"], start, end):
            continue
        w.writerow([s["sold_day"], s["order_id"], s["source"], s["buyer_email"], s["plan"], _rupees(s["amount_paise"]),
                    s["creator_name"] or "(none)", _rupees(s["creator_paise"]), _rupees(s["first_paise"]),
                    _rupees(s["second_paise"]), "yes" if s["refunded"] else "", "yes" if s["creator_paid"] else "",
                    "yes" if s["partners_paid"] else "", s["note"]])
        if s["creator_id"] is not None and not s["refunded"]:
            count += 1
            for i, key in enumerate(("amount_paise", "creator_paise", "first_paise", "second_paise")):
                totals[i] += s[key]
    w.writerow([])
    w.writerow([f"Total ({count} creator sales, refunds excluded)", "", "", "", "", _rupees(totals[0]), "",
                _rupees(totals[1]), _rupees(totals[2]), _rupees(totals[3])])
    return buf.getvalue()


def payouts_csv(start: str = "", end: str = "") -> str:
    first, second = partner_names()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Paid on (IST)", "Type", "Creator", "Period", "Amount ₹", f"{first} ₹", f"{second} ₹", "Sales", "Reference"])
    total = 0
    for p in list_payouts():
        day = _ist_day(p["paid_at"])
        if not _in_range(day, start, end):
            continue
        total += p["amount_paise"]
        w.writerow([day, p["kind"], p["creator_name"] or "", p["period"], _rupees(p["amount_paise"]),
                    _rupees(p["first_paise"]) if p["kind"] == "partner" else "",
                    _rupees(p["second_paise"]) if p["kind"] == "partner" else "", p["sale_count"], p["reference"]])
    w.writerow([])
    w.writerow(["Total paid out", "", "", "", _rupees(total)])
    return buf.getvalue()
