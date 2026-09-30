import { useEffect, useState } from "react";
import { api } from "../api.js";
import SurfaceFrame from "../components/SurfaceFrame.jsx";
import BrandLogo from "../components/BrandLogo.jsx";

function rupees(paise) {
  const n = (Number(paise) || 0) / 100;
  return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function niceDay(iso) {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function niceMonth(ym) {
  const d = new Date(`${ym}-15T12:00:00`);
  return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

function Tab({ id, tab, setTab, children }) {
  return (
    <SurfaceFrame variant={tab === id ? "primary" : "ghost"} size="sm">
      <button type="button" className={tab === id ? "btn btn-primary" : "btn btn-ghost"} onClick={() => setTab(id)}>
        {children}
      </button>
    </SurfaceFrame>
  );
}

const EMPTY_CREATOR = { name: "", email: "", affiliate_code: "", pay_to: "", note: "", active: true };
const EMPTY_SALE = { buyer_email: "", plan: "monthly", amount_rupees: "99", creator_id: "", sold_on: "", order_id: "", note: "" };

export default function Payouts() {
  const [gate, setGate] = useState("checking");
  const [password, setPassword] = useState("");
  const [tab, setTab] = useState("pay");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ text: "", ok: false });
  const [data, setData] = useState(null);
  const [sales, setSales] = useState([]);
  const [history, setHistory] = useState([]);
  const [creatorDraft, setCreatorDraft] = useState(EMPTY_CREATOR);
  const [editingCreator, setEditingCreator] = useState(null);
  const [saleDraft, setSaleDraft] = useState(EMPTY_SALE);
  const [names, setNames] = useState(["", ""]);

  async function load() {
    const [summary, saleData, historyData] = await Promise.all([
      api.payoutsSummary(),
      api.payoutsSales(),
      api.payoutsHistory(),
    ]);
    setData(summary);
    setSales(saleData.sales || []);
    setHistory(historyData.payouts || []);
    setNames(summary.partners || ["", ""]);
    setGate("ok");
  }

  useEffect(() => {
    load().catch((err) => setGate(err.status === 404 ? "missing" : "login"));
  }, []);

  async function run(fn, okText) {
    setBusy(true);
    setMsg({ text: "", ok: false });
    try {
      await fn();
      await load();
      if (okText) setMsg({ text: okText, ok: true });
      return true;
    } catch (err) {
      setMsg({ text: err.message || "Something went wrong.", ok: false });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function login(e) {
    e.preventDefault();
    setBusy(true);
    setMsg({ text: "", ok: false });
    try {
      await api.adminLogin(password);
      setPassword("");
      await load();
    } catch (err) {
      if (err.status === 404) setGate("missing");
      else setMsg({ text: err.message || "Incorrect password.", ok: false });
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await api.adminLogout().catch(() => {});
    setData(null);
    setGate("login");
  }

  function payCreator(g) {
    const ref = window.prompt(
      `Paid ${rupees(g.amount_paise)} to ${g.creator_name} for ${niceDay(g.week_start)} – ${niceDay(g.week_end)}?\n\nUPI / UTR reference (optional):`,
      "",
    );
    if (ref === null) return;
    run(() => api.payoutsPayCreator(g.creator_id, g.week_start, ref), `${g.creator_name} marked paid.`);
  }

  function payPartners(g) {
    const [a, b] = data.partners;
    const ref = window.prompt(
      `Paid ${niceMonth(g.month)}: ${a} ${rupees(g.first_paise)} and ${b} ${rupees(g.second_paise)}?\n\nReference (optional):`,
      "",
    );
    if (ref === null) return;
    run(() => api.payoutsPayPartners(g.month, ref), `${niceMonth(g.month)} partner split marked paid.`);
  }

  function assign(sale, value) {
    if (value === "direct") {
      run(() => api.payoutsUpdateSale(sale.id, { reviewed: true, note: "Direct sale, no creator" }), "Marked as a direct sale.");
    } else if (value) {
      run(() => api.payoutsUpdateSale(sale.id, { creator_id: Number(value) }), "Creator set.");
    }
  }

  function toggleRefund(sale) {
    const next = !sale.refunded;
    const text = next
      ? `Mark this ${rupees(sale.amount_paise)} sale as refunded? Any share already paid is taken back from the next payout.`
      : "Undo the refund on this sale?";
    if (!window.confirm(text)) return;
    run(() => api.payoutsUpdateSale(sale.id, { refunded: next }), next ? "Marked refunded." : "Refund undone.");
  }

  async function saveCreator(e) {
    e.preventDefault();
    const ok = await run(
      () => (editingCreator ? api.payoutsUpdateCreator(editingCreator, creatorDraft) : api.payoutsAddCreator(creatorDraft)),
      editingCreator ? "Creator saved." : "Creator added.",
    );
    if (ok) {
      setCreatorDraft(EMPTY_CREATOR);
      setEditingCreator(null);
    }
  }

  async function addSale(e) {
    e.preventDefault();
    const body = {
      ...saleDraft,
      amount_rupees: Number(saleDraft.amount_rupees) || 0,
      creator_id: saleDraft.creator_id ? Number(saleDraft.creator_id) : null,
    };
    const ok = await run(() => api.payoutsAddSale(body), "Sale added.");
    if (ok) setSaleDraft(EMPTY_SALE);
  }

  async function saveNames(e) {
    e.preventDefault();
    await run(() => api.payoutsSetPartners(names[0].trim(), names[1].trim()), "Names saved.");
  }

  if (gate === "checking") return <div className="boot">Loading…</div>;
  if (gate === "missing") return <div className="boot">Not found.</div>;

  if (gate === "login") {
    return (
      <div className="auth-screen">
        <a className="brand-hero" href="/" aria-label="PyClips home">
          <span className="brand-mark"><BrandLogo size={90} /></span>
          <span className="brand-word">PyClips</span>
        </a>
        <div className="auth-card">
          <h1 className="landing-title" style={{ fontSize: 24 }}>Payouts</h1>
          <p className="landing-sub">Creator sales and payouts. Same password as the admin panel.</p>
          <form className="auth-form" onSubmit={login}>
            <label className="auth-label">
              Password
              <input className="auth-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            </label>
            {msg.text && <p className="error">{msg.text}</p>}
            <SurfaceFrame variant="primary" full>
              <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>{busy ? "Please wait…" : "Log in"}</button>
            </SurfaceFrame>
          </form>
        </div>
      </div>
    );
  }

  const [first, second] = data.partners;
  const creators = data.creators || [];
  const activeCreators = creators.filter((c) => c.active);
  const newCreators = data.new_creators || [];
  const alerts = data.attention.length + newCreators.length;
  const joinLink = `${window.location.origin}/creator-join?sa={affiliate_id}&email={email}&name={first_name}`;
  const creatorDue = data.creator_due.filter((g) => g.status === "due");
  const creatorBuilding = data.creator_due.filter((g) => g.status !== "due");
  const partnerDue = data.partner_due.filter((g) => g.status === "due");
  const partnerBuilding = data.partner_due.filter((g) => g.status !== "due");
  const message = msg.text && <p className={msg.ok ? "note ok" : "error"}>{msg.text}</p>;

  return (
    <div className="page admin-wide">
      <header className="top">
        <a className="brand-inline" href="/" aria-label="PyClips home">
          <span className="brand-mark sm"><BrandLogo size={40} /></span> PyClips Payouts
        </a>
        <SurfaceFrame variant="ghost" size="sm">
          <button type="button" className="btn btn-ghost" onClick={logout} disabled={busy}>Log out</button>
        </SurfaceFrame>
      </header>
      <nav className="admin-nav" aria-label="Payouts">
        <Tab id="pay" tab={tab} setTab={setTab}>To pay{alerts ? ` (${alerts} ⚠)` : ""}</Tab>
        <Tab id="sales" tab={tab} setTab={setTab}>Sales</Tab>
        <Tab id="creators" tab={tab} setTab={setTab}>Creators</Tab>
        <Tab id="history" tab={tab} setTab={setTab}>History</Tab>
      </nav>

      {tab === "pay" && (
        <>
          <h1 className="landing-title">To pay</h1>
          <p className="landing-sub">
            Creators get {data.creator_pct}% of each sale, weekly (Monday–Sunday). At the end of each month, whatever is left after the creators is split 50/50 between {first} and {second}.
          </p>
          <div className="admin-stats">
            <div className="admin-stat">
              <span className="admin-stat-label">Owed to creators now</span>
              <span className="admin-stat-n">{rupees(data.owed_creators_paise)}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Creators, this week so far</span>
              <span className="admin-stat-n">{rupees(data.building_creators_paise)}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Owed to {first} + {second}</span>
              <span className="admin-stat-n">{rupees(data.owed_partners_paise)}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Sales this week</span>
              <span className="admin-stat-n">{data.week_sales}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Sales this month</span>
              <span className="admin-stat-n">{data.month_sales} · {rupees(data.month_gross_paise)}</span>
            </div>
          </div>
          {message}

          {newCreators.length > 0 && (
            <div className="card admin-table-wrap">
              <h2 style={{ margin: 0 }}>New creators joined ({newCreators.length})</h2>
              <p className="note">They signed up from the link in their systeme.io email. Check the name and UPI look right before you pay them.</p>
              <table className="admin-table">
                <thead>
                  <tr><th>Name</th><th>Email</th><th>Affiliate code</th><th>Pay to</th><th></th></tr>
                </thead>
                <tbody>
                  {newCreators.map((c) => (
                    <tr key={c.id}>
                      <td>{c.name}</td>
                      <td>{c.email || "—"}</td>
                      <td>{c.affiliate_code}</td>
                      <td>{c.pay_to}</td>
                      <td className="admin-table-actions">
                        <button type="button" className="btn btn-ghost" disabled={busy}
                          onClick={() => run(() => api.payoutsCreatorChecked(c.id), `${c.name} confirmed.`)}>
                          Looks good
                        </button>
                        <button type="button" className="btn btn-ghost" disabled={busy}
                          onClick={() => { setTab("creators"); setEditingCreator(c.id); setCreatorDraft({ ...EMPTY_CREATOR, ...c }); }}>
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.attention.length > 0 && (
            <div className="card">
              <h2 className="error" style={{ margin: 0 }}>Needs your attention ({data.attention.length})</h2>
              <p className="note">These sales are not counted in any payout until you sort them out.</p>
              <table className="admin-table">
                <thead>
                  <tr><th>Date</th><th>Buyer</th><th>Amount</th><th>Problem</th><th>Fix</th></tr>
                </thead>
                <tbody>
                  {data.attention.map((s) => (
                    <tr key={s.id}>
                      <td>{niceDay(s.sold_day)}</td>
                      <td>{s.buyer_email || "—"}<br /><span className="note">{s.note || s.source_url}</span></td>
                      <td>{rupees(s.amount_paise)} {s.plan}</td>
                      <td>{s.problem}</td>
                      <td className="admin-table-actions">
                        {s.creator_id == null ? (
                          <select className="auth-input" defaultValue="" disabled={busy} onChange={(e) => assign(s, e.target.value)}>
                            <option value="">Pick creator…</option>
                            {activeCreators.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                            <option value="direct">Direct sale (no creator)</option>
                          </select>
                        ) : (
                          <>
                            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => toggleRefund(s)}>Refunded</button>
                            <button type="button" className="btn btn-ghost" disabled={busy}
                              onClick={() => run(() => api.payoutsUpdateSale(s.id, { reviewed: true }), "Kept as a normal sale.")}>
                              Not refunded
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="card admin-table-wrap">
            <h2>Creators: pay weekly</h2>
            {!creatorDue.length && !creatorBuilding.length ? (
              <p className="note">Nothing owed to creators.</p>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr><th>Week</th><th>Creator</th><th>Pay to</th><th>Sales</th><th>Amount</th><th></th></tr>
                </thead>
                <tbody>
                  {[...creatorDue, ...creatorBuilding].map((g) => {
                    const creator = creators.find((c) => c.id === g.creator_id);
                    return (
                      <tr key={`${g.creator_id}-${g.week_start}`}>
                        <td>{niceDay(g.week_start)} – {niceDay(g.week_end)}<br /><span className={g.status === "due" ? "tag-bad" : "note"}>{g.status === "due" ? "Due now" : "Week still running"}</span></td>
                        <td>{g.creator_name}</td>
                        <td>{creator?.pay_to || <span className="tag-bad">No UPI saved</span>}{creator?.needs_check && <><br /><span className="tag-bad">new, check UPI</span></>}</td>
                        <td>{g.sales}</td>
                        <td>
                          {rupees(g.amount_paise)}
                          {g.takeback_paise > 0 && <><br /><span className="note">after taking back {rupees(g.takeback_paise)} refund</span></>}
                        </td>
                        <td className="admin-table-actions">
                          {g.amount_paise < 0 ? (
                            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => payCreator(g)}>Deducted</button>
                          ) : (
                            <SurfaceFrame variant={g.status === "due" ? "primary" : "ghost"} size="sm">
                              <button type="button" className={g.status === "due" ? "btn btn-primary" : "btn btn-ghost"} disabled={busy} onClick={() => payCreator(g)}>Mark paid</button>
                            </SurfaceFrame>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          <div className="card admin-table-wrap">
            <h2>{first} + {second}: pay monthly</h2>
            {!partnerDue.length && !partnerBuilding.length ? (
              <p className="note">Nothing owed to partners.</p>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr><th>Month</th><th>Sales</th><th>Total sales</th><th>Creators 40%</th><th>Left for you two</th><th>{first} (50%)</th><th>{second} (50%)</th><th></th></tr>
                </thead>
                <tbody>
                  {[...partnerDue, ...partnerBuilding].map((g) => (
                    <tr key={g.month}>
                      <td>{niceMonth(g.month)}<br /><span className={g.status === "due" ? "tag-bad" : "note"}>{g.status === "due" ? "Due now" : "Month still running"}</span></td>
                      <td>{g.sales}</td>
                      <td>{rupees(g.gross_paise)}</td>
                      <td>{rupees(g.creator_paise)}</td>
                      <td>{rupees(g.first_paise + g.second_paise)}</td>
                      <td>{rupees(g.first_paise)}</td>
                      <td>{rupees(g.second_paise)}</td>
                      <td className="admin-table-actions">
                        <SurfaceFrame variant={g.status === "due" ? "primary" : "ghost"} size="sm">
                          <button type="button" className={g.status === "due" ? "btn btn-primary" : "btn btn-ghost"} disabled={busy} onClick={() => payPartners(g)}>Mark paid</button>
                        </SurfaceFrame>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {tab === "sales" && (
        <>
          <h1 className="landing-title">Sales</h1>
          <p className="landing-sub">
            Every systeme.io sale lands here on its own, ₹99 monthly and ₹599 lifetime, renewals included.{" "}
            <a href="/api/payouts/export/sales.csv">Download CSV</a>
          </p>
          {message}
          <div className="card admin-table-wrap">
            {!sales.length ? (
              <p className="note">No sales recorded yet.</p>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr><th>Date</th><th>Buyer</th><th>Plan</th><th>Amount</th><th>Creator</th><th>Creator 40%</th><th>{first}</th><th>{second}</th><th>Paid</th><th></th></tr>
                </thead>
                <tbody>
                  {sales.map((s) => (
                    <tr key={s.id} style={s.refunded ? { opacity: 0.55, textDecoration: "line-through" } : undefined}>
                      <td>{niceDay(s.sold_day)}</td>
                      <td>{s.buyer_email || "—"}{s.note && <><br /><span className="note">{s.note}</span></>}</td>
                      <td>{s.plan}{s.source === "manual" ? " (added by hand)" : ""}</td>
                      <td>{rupees(s.amount_paise)}</td>
                      <td>
                        {s.creator_paid ? (s.creator_name || "—") : (
                          <select className="auth-input" value={s.creator_id ?? ""} disabled={busy}
                            onChange={(e) => (e.target.value
                              ? run(() => api.payoutsUpdateSale(s.id, { creator_id: Number(e.target.value) }), "Creator set.")
                              : run(() => api.payoutsUpdateSale(s.id, { clear_creator: true }), "Creator removed."))}>
                            <option value="">None (direct)</option>
                            {creators.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                          </select>
                        )}
                      </td>
                      <td>{s.creator_id != null ? rupees(s.creator_paise) : "—"}</td>
                      <td>{s.creator_id != null ? rupees(s.first_paise) : "—"}</td>
                      <td>{s.creator_id != null ? rupees(s.second_paise) : "—"}</td>
                      <td>{s.creator_paid ? "creator ✓" : ""}{s.creator_paid && s.partners_paid ? " · " : ""}{s.partners_paid ? "partners ✓" : ""}</td>
                      <td className="admin-table-actions">
                        <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => toggleRefund(s)}>
                          {s.refunded ? "Undo refund" : "Refunded"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="card">
            <h2>Add a sale by hand</h2>
            <p className="note">Only for a sale systeme.io did not send (check its Sales page each week).</p>
            <form className="auth-form" onSubmit={addSale}>
              <label className="auth-label">Buyer email
                <input className="auth-input" type="email" value={saleDraft.buyer_email} onChange={(e) => setSaleDraft({ ...saleDraft, buyer_email: e.target.value })} />
              </label>
              <label className="auth-label">Plan
                <select className="auth-input" value={saleDraft.plan}
                  onChange={(e) => setSaleDraft({ ...saleDraft, plan: e.target.value, amount_rupees: e.target.value === "lifetime" ? "599" : "99" })}>
                  <option value="monthly">Monthly ₹99</option>
                  <option value="lifetime">Lifetime ₹599</option>
                </select>
              </label>
              <label className="auth-label">Amount (₹)
                <input className="auth-input" type="number" min={0} step="0.01" value={saleDraft.amount_rupees} onChange={(e) => setSaleDraft({ ...saleDraft, amount_rupees: e.target.value })} required />
              </label>
              <label className="auth-label">Creator
                <select className="auth-input" value={saleDraft.creator_id} onChange={(e) => setSaleDraft({ ...saleDraft, creator_id: e.target.value })} required>
                  <option value="">Pick creator…</option>
                  {activeCreators.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </label>
              <label className="auth-label">Date
                <input className="auth-input" type="date" value={saleDraft.sold_on} onChange={(e) => setSaleDraft({ ...saleDraft, sold_on: e.target.value })} required />
              </label>
              <label className="auth-label">systeme.io order number (optional, stops double entry)
                <input className="auth-input" value={saleDraft.order_id} onChange={(e) => setSaleDraft({ ...saleDraft, order_id: e.target.value })} />
              </label>
              <label className="auth-label">Note
                <input className="auth-input" value={saleDraft.note} onChange={(e) => setSaleDraft({ ...saleDraft, note: e.target.value })} />
              </label>
              <SurfaceFrame variant="primary" full>
                <button className="btn btn-primary" type="submit" disabled={busy}>Add sale</button>
              </SurfaceFrame>
            </form>
          </div>
        </>
      )}

      {tab === "creators" && (
        <>
          <h1 className="landing-title">Creators</h1>
          <p className="landing-sub">
            The affiliate code is the part after <code>sa=</code> in the creator's             systeme.io affiliate link. Sales carrying it are matched automatically.
          </p>
          {message}
          <div className="card">
            <h2>Add creators automatically</h2>
            <p className="note">
              Put this link in the email systeme.io sends after someone signs up on your Affiliate Signup funnel.
              systeme.io fills in each creator's own code, email and name; they only type their UPI and appear here.
              If systeme.io's variable picker shows different names, use its affiliate ID, email and first name variables.
            </p>
            <input className="auth-input" value={joinLink} readOnly onFocus={(e) => e.target.select()} />
            <SurfaceFrame variant="ghost" size="sm">
              <button type="button" className="btn btn-ghost"
                onClick={() => navigator.clipboard.writeText(joinLink).then(() => setMsg({ text: "Link copied.", ok: true }))}>
                Copy link
              </button>
            </SurfaceFrame>
          </div>
          <div className="card admin-table-wrap">
            {!creators.length ? (
              <p className="note">No creators yet. Add them below.</p>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr><th>Name</th><th>Email</th><th>Affiliate code</th><th>Pay to</th><th>Status</th><th></th></tr>
                </thead>
                <tbody>
                  {creators.map((c) => (
                    <tr key={c.id}>
                      <td>{c.name}</td>
                      <td>{c.email}</td>
                      <td>{c.affiliate_code || <span className="tag-bad">missing</span>}</td>
                      <td>{c.pay_to || <span className="tag-bad">missing</span>}</td>
                      <td>{c.active ? "active" : "stopped"}{c.needs_check && <><br /><span className="tag-bad">new, check</span></>}</td>
                      <td className="admin-table-actions">
                        <button type="button" className="btn btn-ghost" disabled={busy}
                          onClick={() => { setEditingCreator(c.id); setCreatorDraft({ ...EMPTY_CREATOR, ...c }); }}>
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="card">
            <h2>{editingCreator ? "Edit creator" : "Add a creator"}</h2>
            <form className="auth-form" onSubmit={saveCreator}>
              <label className="auth-label">Name
                <input className="auth-input" value={creatorDraft.name} onChange={(e) => setCreatorDraft({ ...creatorDraft, name: e.target.value })} required />
              </label>
              <label className="auth-label">Email (their systeme.io affiliate email)
                <input className="auth-input" type="email" value={creatorDraft.email} onChange={(e) => setCreatorDraft({ ...creatorDraft, email: e.target.value })} />
              </label>
              <label className="auth-label">Affiliate code (after sa= in their link)
                <input className="auth-input" value={creatorDraft.affiliate_code} onChange={(e) => setCreatorDraft({ ...creatorDraft, affiliate_code: e.target.value })} placeholder="sa0012345..." />
              </label>
              <label className="auth-label">Pay to (UPI ID or bank details)
                <input className="auth-input" value={creatorDraft.pay_to} onChange={(e) => setCreatorDraft({ ...creatorDraft, pay_to: e.target.value })} placeholder="name@upi" />
              </label>
              <label className="auth-label">Note
                <input className="auth-input" value={creatorDraft.note} onChange={(e) => setCreatorDraft({ ...creatorDraft, note: e.target.value })} />
              </label>
              <label className="auth-label" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={creatorDraft.active} onChange={(e) => setCreatorDraft({ ...creatorDraft, active: e.target.checked })} />
                Active (still promoting)
              </label>
              <SurfaceFrame variant="primary" full>
                <button className="btn btn-primary" type="submit" disabled={busy}>{editingCreator ? "Save creator" : "Add creator"}</button>
              </SurfaceFrame>
              {editingCreator && (
                <button type="button" className="btn btn-ghost" onClick={() => { setEditingCreator(null); setCreatorDraft(EMPTY_CREATOR); }}>Cancel</button>
              )}
            </form>
          </div>
          <div className="card">
            <h2>Partner names</h2>
            <form className="auth-form" onSubmit={saveNames}>
              <label className="auth-label">First partner
                <input className="auth-input" value={names[0]} onChange={(e) => setNames([e.target.value, names[1]])} required />
              </label>
              <label className="auth-label">Second partner
                <input className="auth-input" value={names[1]} onChange={(e) => setNames([names[0], e.target.value])} required />
              </label>
              <SurfaceFrame variant="primary" full>
                <button className="btn btn-primary" type="submit" disabled={busy}>Save names</button>
              </SurfaceFrame>
            </form>
          </div>
        </>
      )}

      {tab === "history" && (
        <>
          <h1 className="landing-title">History</h1>
          <p className="landing-sub">Every payout you marked paid. <a href="/api/payouts/export/payouts.csv">Download CSV</a></p>
          <div className="card admin-table-wrap">
            {!history.length ? (
              <p className="note">No payouts yet.</p>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr><th>Paid on</th><th>Who</th><th>For</th><th>Sales</th><th>Amount</th><th>Reference</th></tr>
                </thead>
                <tbody>
                  {history.map((p) => (
                    <tr key={p.id}>
                      <td>{niceDay(p.paid_at)}</td>
                      <td>{p.kind === "creator" ? p.creator_name : `${first} ${rupees(p.first_paise)} · ${second} ${rupees(p.second_paise)}`}</td>
                      <td>{p.kind === "creator" ? `week of ${niceDay(p.period)}` : niceMonth(p.period)}</td>
                      <td>{p.sale_count}</td>
                      <td>{rupees(p.amount_paise)}</td>
                      <td>{p.reference}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
