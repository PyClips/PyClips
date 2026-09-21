import { useEffect, useState } from "react";
import { api } from "../api.js";
import SurfaceFrame from "../components/SurfaceFrame.jsx";
import BrandLogo from "../components/BrandLogo.jsx";

function BrandHome({ large = false }) {
  if (large) {
    return (
      <a className="brand-hero" href="/" aria-label="PyClips home">
        <span className="brand-mark"><BrandLogo size={90} /></span>
        <span className="brand-word">PyClips</span>
      </a>
    );
  }
  return (
    <a className="brand-inline" href="/" aria-label="PyClips home">
      <span className="brand-mark sm"><BrandLogo size={40} /></span> PyClips
    </a>
  );
}

function LegalFooter() {
  return (
    <p className="legal-foot">
      <a href="/privacy">Privacy</a>
    </p>
  );
}

function untilDate(iso) {
  if (!iso) return "";
  const text = String(iso);
  if (text.length >= 10) return text.slice(0, 10);
  return "";
}

function draftFromUser(row) {
  return {
    email: row.email || "",
    username: row.username || "",
    plan: row.plan || "free",
    billing_plan: row.billing_plan || "",
    videos_used: String(row.videos_used ?? 0),
    premium_until: untilDate(row.premium_until),
  };
}

function TabButton({ id, tab, setTab, setMsg, children }) {
  return (
    <SurfaceFrame variant={tab === id ? "primary" : "ghost"} size="sm">
      <button
        type="button"
        className={tab === id ? "btn btn-primary" : "btn btn-ghost"}
        onClick={() => { setTab(id); setMsg(""); }}
      >
        {children}
      </button>
    </SurfaceFrame>
  );
}

export default function Admin() {
  const [gate, setGate] = useState("checking");
  const [tab, setTab] = useState("overview");
  const [password, setPassword] = useState("");
  const [months, setMonths] = useState(1);
  const [maxPeople, setMaxPeople] = useState(1);
  const [customCode, setCustomCode] = useState("");
  const [coupons, setCoupons] = useState([]);
  const [storage, setStorage] = useState(null);
  const [created, setCreated] = useState("");
  const [copied, setCopied] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [downloadMeta, setDownloadMeta] = useState(null);
  const [stats, setStats] = useState(null);
  const [hitsDraft, setHitsDraft] = useState("0");
  const [users, setUsers] = useState([]);
  const [userTotal, setUserTotal] = useState(0);
  const [userQuery, setUserQuery] = useState("");
  const [userPlan, setUserPlan] = useState("all");
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState(null);

  async function loadUsers(q = userQuery, plan = userPlan) {
    const data = await api.adminUsers((q || "").trim(), 0, plan || "all");
    setUsers(data.users || []);
    setUserTotal(data.total || 0);
    return data;
  }

  async function loadAdmin(plan = userPlan) {
    const [couponData, downloadData, overviewData, userData] = await Promise.all([
      api.adminCoupons(),
      api.adminDownload(),
      api.adminOverview(),
      api.adminUsers(userQuery.trim(), 0, plan || "all"),
    ]);
    setCoupons(couponData.coupons || []);
    setStorage(couponData.storage || overviewData.storage || null);
    setDownloadMeta(downloadData);
    setDownloadUrl(downloadData.url || "");
    setStats(overviewData);
    setHitsDraft(String(overviewData.website_downloads ?? 0));
    setUsers(userData.users || []);
    setUserTotal(userData.total || 0);
    setGate("ok");
  }

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        await loadAdmin();
      } catch (err) {
        if (!live) return;
        if (err.status === 404) setGate("missing");
        else setGate("login");
      }
    })();
    return () => { live = false; };
  }, []);

  async function login(e) {
    e.preventDefault();
    setMsg("");
    setBusy(true);
    try {
      await api.adminLogin(password);
      setPassword("");
      await loadAdmin();
    } catch (err) {
      if (err.status === 404) setGate("missing");
      else setMsg(err.message || "Incorrect password.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    try {
      await api.adminLogout();
    } finally {
      setBusy(false);
      setCoupons([]);
      setStorage(null);
      setCreated("");
      setCustomCode("");
      setDownloadUrl("");
      setDownloadMeta(null);
      setStats(null);
      setUsers([]);
      setUserTotal(0);
      setUserQuery("");
      setUserPlan("all");
      setEditingId(null);
      setDraft(null);
      setTab("overview");
      setGate("login");
    }
  }

  async function searchUsers(e) {
    if (e) e.preventDefault();
    setMsg("");
    setBusy(true);
    try {
      await loadUsers(userQuery, userPlan);
      setEditingId(null);
      setDraft(null);
    } catch (err) {
      setMsg(err.message || "Could not load accounts.");
    } finally {
      setBusy(false);
    }
  }

  async function filterUsers(plan) {
    setUserPlan(plan);
    setMsg("");
    setBusy(true);
    try {
      await loadUsers(userQuery, plan);
      setEditingId(null);
      setDraft(null);
    } catch (err) {
      setMsg(err.message || "Could not load accounts.");
    } finally {
      setBusy(false);
    }
  }

  async function saveHits(e) {
    e.preventDefault();
    setMsg("");
    setBusy(true);
    try {
      const data = await api.adminSetDownloadHits(hitsDraft);
      setHitsDraft(String(data.hits ?? 0));
      const overviewData = await api.adminOverview();
      setStats(overviewData);
      setMsg("Website download count saved.");
    } catch (err) {
      setMsg(err.message || "Could not save that count.");
    } finally {
      setBusy(false);
    }
  }

  async function saveUser(e) {
    e.preventDefault();
    if (!editingId || !draft) return;
    setMsg("");
    setBusy(true);
    try {
      const savedPlan = draft.plan;
      await api.adminUpdateUser(editingId, {
        email: draft.email.trim(),
        username: draft.username.trim(),
        plan: savedPlan,
        billing_plan: savedPlan === "premium" ? "admin" : "",
        videos_used: Number(draft.videos_used) || 0,
        premium_until: draft.premium_until,
      });
      setEditingId(null);
      setDraft(null);
      const nextFilter = userPlan !== "all" && savedPlan !== userPlan ? "all" : userPlan;
      setUserPlan(nextFilter);
      await loadAdmin(nextFilter);
      setMsg("Account saved.");
    } catch (err) {
      setMsg(err.message || "Could not save that account.");
    } finally {
      setBusy(false);
    }
  }

  async function removeUser(row) {
    if (!window.confirm(`Delete ${row.email}? This removes the account, payments, and redeem history for that person.`)) {
      return;
    }
    setMsg("");
    setBusy(true);
    try {
      await api.adminDeleteUser(row.id);
      if (editingId === row.id) {
        setEditingId(null);
        setDraft(null);
      }
      await loadAdmin(userPlan);
    } catch (err) {
      setMsg(err.message || "Could not delete that account.");
    } finally {
      setBusy(false);
    }
  }

  async function create(e) {
    e.preventDefault();
    setMsg("");
    setBusy(true);
    try {
      const row = await api.adminCreate(Number(months), Number(maxPeople), customCode.trim());
      setCreated(row.code || "");
      setCustomCode("");
      await loadAdmin();
    } catch (err) {
      setMsg(err.message || "Could not create that code.");
    } finally {
      setBusy(false);
    }
  }

  async function removeCode(code) {
    if (!window.confirm(`Delete ${code}? New people will not be able to redeem it. Accounts that already used it keep Premium.`)) {
      return;
    }
    setMsg("");
    setBusy(true);
    try {
      await api.adminDelete(code);
      if (created === code) setCreated("");
      await loadAdmin();
    } catch (err) {
      setMsg(err.message || "Could not delete that code.");
    } finally {
      setBusy(false);
    }
  }

  async function copyCode(code) {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(code);
      setTimeout(() => setCopied((cur) => (cur === code ? "" : cur)), 1600);
    } catch {
      setMsg("Could not copy. Select the code and copy it yourself.");
    }
  }

  async function saveDownload(e) {
    e.preventDefault();
    setMsg("");
    setBusy(true);
    try {
      const data = await api.adminSetDownload(downloadUrl.trim());
      setDownloadMeta(data);
      setDownloadUrl(data.url || "");
      setMsg("Download button is live on the landing page.");
    } catch (err) {
      setMsg(err.message || "Could not save that download URL.");
    } finally {
      setBusy(false);
    }
  }

  async function clearDownload() {
    if (!window.confirm("Remove the landing download link? The button will show Coming soon until you save a new URL.")) {
      return;
    }
    setMsg("");
    setBusy(true);
    try {
      const data = await api.adminClearDownload();
      setDownloadMeta(data);
      setDownloadUrl("");
    } catch (err) {
      setMsg(err.message || "Could not clear the download URL.");
    } finally {
      setBusy(false);
    }
  }

  if (gate === "checking") return <div className="boot">Loading…</div>;
  if (gate === "missing") return <div className="boot">Not found.</div>;

  if (gate === "login") {
    return (
      <div className="auth-screen">
        <BrandHome large />
        <div className="auth-card">
          <h1 className="landing-title" style={{ fontSize: 24 }}>Admin</h1>
          <p className="landing-sub">Dashboard, accounts, redeem codes, and the Windows download link. Not a public account page.</p>
          <form className="auth-form" onSubmit={login}>
            <label className="auth-label">
              Password
              <input className="auth-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            </label>
            {msg && <p className="error">{msg}</p>}
            <SurfaceFrame variant="primary" full>
              <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>{busy ? "Please wait…" : "Log in"}</button>
            </SurfaceFrame>
          </form>
        </div>
        <LegalFooter />
      </div>
    );
  }

  const okMsg = msg && (msg.includes("live") || msg.includes("saved") || msg.includes("Account saved") || msg.includes("count saved"));

  return (
    <div className="page admin-wide">
      <header className="top">
        <BrandHome />
        <SurfaceFrame variant="ghost" size="sm">
          <button type="button" className="btn btn-ghost" onClick={logout} disabled={busy}>Log out</button>
        </SurfaceFrame>
      </header>
      <nav className="admin-nav" aria-label="Admin">
        <TabButton id="overview" tab={tab} setTab={setTab} setMsg={setMsg}>Dashboard</TabButton>
        <TabButton id="accounts" tab={tab} setTab={setTab} setMsg={setMsg}>Accounts</TabButton>
        <TabButton id="codes" tab={tab} setTab={setTab} setMsg={setMsg}>Redeem codes</TabButton>
        <TabButton id="download" tab={tab} setTab={setTab} setMsg={setMsg}>Download</TabButton>
      </nav>

      {tab === "overview" && (
        <>
          <h1 className="landing-title">Dashboard</h1>
          <p className="landing-sub">Live numbers from the pyclips.in database. Edit accounts on the Accounts tab.</p>
          {storage?.ephemeral && (
            <p className="error">
              This data sits on a temporary disk. Attach a Railway volume at <code>/data</code> or it will vanish on the next deploy.
            </p>
          )}
          <div className="admin-stats">
            <div className="admin-stat">
              <span className="admin-stat-label">Signed-in accounts</span>
              <span className="admin-stat-n">{stats?.accounts ?? 0}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Google</span>
              <span className="admin-stat-n">{stats?.google_logins ?? 0}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Email</span>
              <span className="admin-stat-n">{stats?.email_logins ?? 0}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Premium</span>
              <span className="admin-stat-n">{stats?.premium ?? 0}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Free</span>
              <span className="admin-stat-n">{stats?.free ?? 0}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Website Setup clicks</span>
              <span className="admin-stat-n">{stats?.website_downloads ?? 0}</span>
            </div>
            <div className="admin-stat">
              <span className="admin-stat-label">Recorded payments</span>
              <span className="admin-stat-n">{stats?.payments ?? 0}</span>
            </div>
          </div>
          <div className="card">
            <h2>Website download count</h2>
            <p className="note">Counts each visit to pyclips.in/download after this counter started. It does not include Microsoft Store installs.</p>
            <form className="auth-form" onSubmit={saveHits}>
              <label className="auth-label">
                Clicks
                <input className="auth-input" type="number" min={0} value={hitsDraft} onChange={(e) => setHitsDraft(e.target.value)} required />
              </label>
              {msg && tab === "overview" && <p className={okMsg ? "note ok" : "error"}>{msg}</p>}
              <SurfaceFrame variant="primary" full>
                <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save count"}</button>
              </SurfaceFrame>
            </form>
          </div>
          <div className="card">
            <h2>What these numbers are</h2>
            {(stats?.notes || []).map((line) => (
              <p className="note" key={line}>{line}</p>
            ))}
          </div>
          <LegalFooter />
        </>
      )}

      {tab === "accounts" && (
        <>
          <h1 className="landing-title">Accounts</h1>
          <p className="landing-sub">
            {userPlan === "premium"
              ? `${userTotal} ${userTotal === 1 ? "premium account" : "premium accounts"}. Search, edit plan, or delete.`
              : userPlan === "free"
                ? `${userTotal} ${userTotal === 1 ? "free account" : "free accounts"}. Search, edit plan, or delete.`
                : `${userTotal} ${userTotal === 1 ? "account" : "accounts"} in the database. Search, edit plan, or delete.`}
          </p>
          <div className="admin-plan-filters" role="group" aria-label="Filter accounts by plan">
            <TabButton id="all" tab={userPlan} setTab={filterUsers} setMsg={setMsg}>All</TabButton>
            <TabButton id="premium" tab={userPlan} setTab={filterUsers} setMsg={setMsg}>Premium</TabButton>
            <TabButton id="free" tab={userPlan} setTab={filterUsers} setMsg={setMsg}>Free</TabButton>
          </div>
          <form className="admin-search" onSubmit={searchUsers}>
            <input
              className="auth-input"
              placeholder="Search email or username"
              value={userQuery}
              onChange={(e) => setUserQuery(e.target.value)}
            />
            <SurfaceFrame variant="primary" size="sm">
              <button className="btn btn-primary" type="submit" disabled={busy}>Search</button>
            </SurfaceFrame>
          </form>
          {msg && tab === "accounts" && <p className={okMsg ? "note ok" : "error"}>{msg}</p>}
          <div className="card admin-table-wrap">
            {!users.length ? (
              <p className="note">No accounts match.</p>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Username</th>
                    <th>Sign-in</th>
                    <th>Plan</th>
                    <th>Until</th>
                    <th>Clips used</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((row) => (
                    <tr key={row.id}>
                      <td>{row.email}</td>
                      <td>{row.username}</td>
                      <td>{row.sign_in}</td>
                      <td>{row.plan}</td>
                      <td>{untilDate(row.premium_until) || "—"}</td>
                      <td>{row.videos_used}</td>
                      <td className="admin-table-actions">
                        <SurfaceFrame variant="ghost" size="sm">
                          <button
                            type="button"
                            className="btn btn-ghost"
                            disabled={busy}
                            onClick={() => {
                              setEditingId(row.id);
                              setDraft(draftFromUser(row));
                              setMsg("");
                            }}
                          >
                            Edit
                          </button>
                        </SurfaceFrame>
                        <SurfaceFrame variant="ghost" size="sm">
                          <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => removeUser(row)}>
                            Delete
                          </button>
                        </SurfaceFrame>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {editingId && draft && (
            <div className="card">
              <h2>Edit account</h2>
              <form className="auth-form" onSubmit={saveUser}>
                <label className="auth-label">
                  Email
                  <input className="auth-input" type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} required />
                </label>
                <label className="auth-label">
                  Username
                  <input className="auth-input" value={draft.username} onChange={(e) => setDraft({ ...draft, username: e.target.value })} required minLength={3} maxLength={24} />
                </label>
                <label className="auth-label">
                  Plan
                  <select className="auth-input" value={draft.plan} onChange={(e) => setDraft({ ...draft, plan: e.target.value })}>
                    <option value="free">free</option>
                    <option value="premium">premium</option>
                  </select>
                </label>
                <label className="auth-label">
                  Billing
                  <select className="auth-input" value={draft.billing_plan} onChange={(e) => setDraft({ ...draft, billing_plan: e.target.value })}>
                    <option value="">none</option>
                    <option value="admin">admin grant</option>
                    <option value="monthly">monthly</option>
                    <option value="yearly">yearly</option>
                    <option value="coupon">coupon</option>
                  </select>
                </label>
                <label className="auth-label">
                  Premium until
                  <input className="auth-input" type="date" value={draft.premium_until} onChange={(e) => setDraft({ ...draft, premium_until: e.target.value })} />
                </label>
                <p className="note">Premium saved here stays until that date. Leave billing on none (or admin grant) so opening the app does not undo it.</p>
                <label className="auth-label">
                  Clips used
                  <input className="auth-input" type="number" min={0} value={draft.videos_used} onChange={(e) => setDraft({ ...draft, videos_used: e.target.value })} required />
                </label>
                <div className="admin-edit-actions">
                  <SurfaceFrame variant="primary" size="sm">
                    <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
                  </SurfaceFrame>
                  <SurfaceFrame variant="ghost" size="sm">
                    <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => { setEditingId(null); setDraft(null); }}>
                      Cancel
                    </button>
                  </SurfaceFrame>
                </div>
              </form>
            </div>
          )}
          <LegalFooter />
        </>
      )}

      {tab === "download" && (
        <>
          <h1 className="landing-title">Download</h1>
          <p className="landing-sub">Paste the GitHub Releases .exe URL. Landing “Download PyClips” buttons then start that download.</p>
          {storage?.ephemeral && (
            <p className="error">
              This link is stored on a temporary disk. Attach a Railway volume at <code>/data</code> or it will vanish on the next deploy.
            </p>
          )}
          <div className="card">
            <h2>Windows installer</h2>
            <p className="note">
              On GitHub: Releases → attach <code>PyClips-Setup-….exe</code> → copy the asset URL
              (<code>https://github.com/…/releases/download/…/PyClips-Setup-….exe</code>).
            </p>
            <p className="note">Website Setup clicks so far: <b>{downloadMeta?.hits ?? stats?.website_downloads ?? 0}</b></p>
            <form className="auth-form" onSubmit={saveDownload}>
              <label className="auth-label">
                GitHub Releases URL
                <input
                  className="auth-input"
                  type="url"
                  placeholder="https://github.com/PyClips/PyClips/releases/download/desktop-1.0.20/PyClips-Setup-1.0.20.exe"
                  value={downloadUrl}
                  onChange={(e) => setDownloadUrl(e.target.value)}
                  required
                />
              </label>
              {msg && tab === "download" && <p className={okMsg ? "note ok" : "error"}>{msg}</p>}
              <SurfaceFrame variant="primary" full>
                <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save and publish"}</button>
              </SurfaceFrame>
            </form>
            {downloadMeta?.url ? (
              <div style={{ marginTop: 16 }}>
                <p className="note ok">Live: {downloadMeta.filename || "Windows installer"}</p>
                <p className="note"><a href="/download">pyclips.in/download</a> redirects to that file.</p>
                <SurfaceFrame variant="ghost" size="sm">
                  <button type="button" className="btn btn-ghost" disabled={busy} onClick={clearDownload}>Clear</button>
                </SurfaceFrame>
              </div>
            ) : (
              <p className="note" style={{ marginTop: 16 }}>No installer linked. Landing shows Coming soon.</p>
            )}
          </div>
          <LegalFooter />
        </>
      )}

      {tab === "codes" && (
        <>
          <h1 className="landing-title">Redeem codes</h1>
          <p className="landing-sub">Create a code, set months of Premium, and how many people can use it.</p>
          {storage?.ephemeral && (
            <p className="error">
              These codes sit on a temporary disk. Railway wipes unused codes on every deploy — that is why yesterday’s code disappeared. In Railway: create a volume, mount it at <code>/data</code>, set <code>PYCLIPS_DATA_DIR=/data</code>, then redeploy. Accounts that already redeemed keep Premium.
            </p>
          )}
          <div className="card">
            <h2>Create code</h2>
            <form className="auth-form" onSubmit={create}>
              <label className="auth-label">
                Creator code (optional)
                <input
                  className="auth-input"
                  placeholder="Sourav15 or harshxyz — leave blank for a random code"
                  value={customCode}
                  onChange={(e) => setCustomCode(e.target.value)}
                  minLength={3}
                  maxLength={32}
                />
              </label>
              <label className="auth-label">
                Months
                <input className="auth-input" type="number" min={1} max={24} value={months} onChange={(e) => setMonths(e.target.value)} required />
              </label>
              <label className="auth-label">
                Max people
                <input className="auth-input" type="number" min={1} max={10000} value={maxPeople} onChange={(e) => setMaxPeople(e.target.value)} required />
              </label>
              {msg && tab === "codes" && <p className="error">{msg}</p>}
              <SurfaceFrame variant="primary" full>
                <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Creating…" : "Create code"}</button>
              </SurfaceFrame>
            </form>
            {created && (
              <div className="admin-code">
                <code>{created}</code>
                <SurfaceFrame variant="primary" size="sm">
                  <button type="button" className="btn btn-primary" onClick={() => copyCode(created)}>
                    {copied === created ? "Copied" : "Copy"}
                  </button>
                </SurfaceFrame>
              </div>
            )}
          </div>
          <div className="card">
            <h2>Existing codes</h2>
            {!coupons.length ? <p className="note">No codes yet.</p> : coupons.map((row) => {
              const maxLabel = row.max_redemptions == null ? "Unlimited" : String(row.max_redemptions);
              const monthLabel = row.months == null ? "—" : `${row.months} month${row.months === 1 ? "" : "s"}`;
              const archived = Boolean(row.archived);
              return (
                <div className="row" key={row.code} style={{ alignItems: "center", opacity: archived ? 0.7 : 1 }}>
                  <code className="admin-code-inline">{row.code}</code>
                  <span>{archived ? "Removed" : monthLabel}</span>
                  <b>{row.used} / {maxLabel}</b>
                  <SurfaceFrame variant="ghost" size="sm">
                    <button type="button" className="btn btn-ghost" onClick={() => copyCode(row.code)}>
                      {copied === row.code ? "Copied" : "Copy"}
                    </button>
                  </SurfaceFrame>
                  {!archived && (
                    <SurfaceFrame variant="ghost" size="sm">
                      <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => removeCode(row.code)}>
                        Delete
                      </button>
                    </SurfaceFrame>
                  )}
                </div>
              );
            })}
          </div>
          <LegalFooter />
        </>
      )}
    </div>
  );
}
