import { useEffect, useState } from "react";
import { api, loadRazorpay } from "./api.js";
import SurfaceFrame from "./components/SurfaceFrame.jsx";
import AuthPanel from "./components/AuthPanel.jsx";
import BrandLogo from "./components/BrandLogo.jsx";
import Landing from "./pages/Landing.jsx";

function pathOf() {
  return window.location.pathname.replace(/\/$/, "") || "/";
}

function qs(name) {
  return new URLSearchParams(window.location.search).get(name) || "";
}

function untilLabel(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return iso.slice(0, 10);
  }
}

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

function Privacy() {
  useEffect(() => { document.title = "Privacy · PyClips"; }, []);
  return (
    <div className="page legal">
      <header className="top">
        <BrandHome />
      </header>
      <h1 className="landing-title">Privacy policy</h1>
      <p className="landing-sub">Last updated 25 August 2026. This page explains what PyClips collects and why.</p>

      <div className="card">
        <h2>Who we are</h2>
        <p>
          PyClips is a desktop video clipping app plus this website at <a href="https://pyclips.in">pyclips.in</a>.
          Clip rendering and transcription run in the Windows app. This website is for accounts, Premium, and redeem codes.
        </p>
      </div>

      <div className="card">
        <h2>Account information</h2>
        <p>
          When you create an account we store your email, username, password hash (if you sign up with email),
          and optionally your Google account id if you use Continue with Google. We use this to sign you in,
          attach Premium, and sync that status to the PyClips desktop app on the same email.
        </p>
      </div>

      <div className="card">
        <h2>Google sign-in</h2>
        <p>
          Google login is handled by Google. We receive your Google user id and email so we can create or link a PyClips account.
          We do not receive your Google password. Google’s own policy applies to that sign-in:{" "}
          <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">Google Privacy Policy</a>.
        </p>
      </div>

      <div className="card">
        <h2>Payments</h2>
        <p>
          Premium is billed in INR for India or USD outside India, both through Razorpay (including Razorpay International for non-India cards). Typical list prices are ₹29 / month or ₹199 / year in India, and $2.99 / month or $29.99 / year elsewhere. We store your plan, how long Premium lasts, and Razorpay customer/subscription ids needed to keep autopay working and to show your status.
          We do not store full card numbers. Razorpay’s policy:{" "}
          <a href="https://razorpay.com/privacy/" target="_blank" rel="noreferrer">Razorpay Privacy Policy</a>.
          You can cancel autopay from Razorpay or your bank / card issuer.
        </p>
      </div>

      <div className="card">
        <h2>Terms of purchase</h2>
        <p>
          Premium unlocks unlimited clip generations and premium desktop features for the paid period. India charges are in INR; charges outside India are in USD via Razorpay International. Prices are list prices (not a live FX conversion). Failed payments do not grant Premium. When a subscription is cancelled or ends, Premium access ends according to the provider’s billing period. Taxes may be collected by the payment provider where applicable. Microsoft Store listings do not sell Premium inside the Store window — checkout always happens on pyclips.in.
        </p>
      </div>

      <div className="card">
        <h2>Redeem codes</h2>
        <p>
          If you redeem a code, we record that your account used that code so it cannot be reused on the same account,
          and we grant Premium for the duration of the code. We do not publish who used which promotional code.
        </p>
      </div>

      <div className="card">
        <h2>Desktop app and your videos</h2>
        <p>
          Source videos, transcripts, and exported clips are handled in the desktop app, not stored on pyclips.in.
          The app may send your email, clip usage count, and a sync token to this website so Premium and free-tier limits stay in sync.
        </p>
      </div>

      <div className="card">
        <h2>Cookies and logs</h2>
        <p>
          This website uses an http-only session cookie to keep you signed in, and a short-lived admin cookie for the
          internal redeem-code page. The desktop app may write log files for crashes and download errors.
          We do not run advertising trackers on this site.
        </p>
      </div>

      <div className="card">
        <h2>How long we keep data</h2>
        <p>
          We keep account and subscription records while your account exists, and payment references as needed for billing and fraud prevention.
          You can stop using PyClips at any time. To delete an account, contact us from the email on that account via the PyClips website.
        </p>
      </div>

      <div className="card">
        <h2>Contact</h2>
        <p>
          Questions about this policy: open <a href="https://pyclips.in">pyclips.in</a> signed in with your PyClips email.
        </p>
      </div>
    </div>
  );
}

function Account({ user, sub, setSub, setUser }) {
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const premium = sub?.plan === "premium";
  const used = sub?.videos_used ?? 0;
  const limit = sub?.videos_limit;
  const usageLabel = premium || limit == null ? `${used} clips generated` : `${used} / ${limit} clips generated`;
  const showTest = Boolean(sub?.test_mode && sub?.payments_enabled);
  const msgOk = msg === "Code applied. Premium is active.";

  useEffect(() => {
    document.title = "Account · PyClips";
  }, []);

  async function redeem(e) {
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const data = await api.redeem(code.trim());
      setSub(data.subscription);
      if (data.user) setUser(data.user);
      setCode("");
      setMsg("Code applied. Premium is active.");
    } catch (err) {
      setMsg(err.message || "Could not apply that code.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await api.logout();
    window.location.href = "/";
  }

  return (
    <div className="account-studio">
      <header className="account-studio__nav">
        <BrandHome />
        <button type="button" className="account-studio__logout" onClick={logout}>
          Log out
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </header>

      <main className="account-studio__main">
        <section className="account-studio__card" aria-labelledby="account-heading">
          <h2 id="account-heading">Account</h2>
          <div className="account-studio__rows">
            <div className="account-studio__row">
              <span>Username</span>
              <b>{user.username}</b>
            </div>
            <div className="account-studio__row">
              <span>Email</span>
              <b>{user.email}</b>
            </div>
          </div>
        </section>

        <section className="account-studio__card" aria-labelledby="sub-heading">
          <h2 id="sub-heading">Subscription</h2>
          <div className="account-studio__rows">
            <div className="account-studio__row">
              <span>Plan</span>
              <b className="account-studio__pills">
                <em className={"account-studio__pill" + (premium ? " is-premium" : "")}>
                  {premium ? "Premium" : "Free"}
                </em>
                {showTest ? <em className="account-studio__pill is-test">test</em> : null}
              </b>
            </div>
            <div className="account-studio__row">
              <span>Usage</span>
              <b>{usageLabel}</b>
            </div>
            {premium && sub.premium_until && (
              <div className="account-studio__row">
                <span>Active until</span>
                <b>{untilLabel(sub.premium_until)}{sub.days_left != null ? ` · ${sub.days_left}d left` : ""}</b>
              </div>
            )}
          </div>

          <p className="account-studio__note">
            Free accounts can generate 10 clips (lifetime; deleting a clip does not restore a slot).
            Premium uses Razorpay autopay — INR in India, USD elsewhere (Razorpay International).
          </p>

          <a className="account-studio__pay" href="/pay">
            Purchase Premium
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </a>

          <div className="account-studio__divider" />

          <form className="account-studio__redeem" onSubmit={redeem}>
            <span className="account-studio__redeem-label">Redeem code</span>
            <div className="account-studio__redeem-row">
              <input
                className="account-studio__input"
                placeholder="Have a code?"
                value={code}
                autoComplete="off"
                spellCheck="false"
                onChange={(e) => { setCode(e.target.value); setMsg(""); }}
              />
              <button type="submit" disabled={busy || !code.trim()}>
                {busy ? "Please wait…" : "Redeem"}
              </button>
            </div>
            {msg ? (
              <p className={"account-studio__msg" + (msgOk ? " is-ok" : " is-err")}>{msg}</p>
            ) : null}
          </form>
        </section>
      </main>

      <footer className="account-studio__foot">
        <span>© 2026 PyClips</span>
        <span aria-hidden="true">·</span>
        <a href="/privacy">Privacy</a>
      </footer>
    </div>
  );
}

function Pay({ user, sub, ticket, defaultPlan, lockedEmail, setSub, setUser }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [pricing, setPricing] = useState(null);
  const premium = sub?.plan === "premium";
  const billingPlan = sub?.billing_plan;
  const currencyOverride = (qs("currency") || "").toUpperCase();

  useEffect(() => {
    let live = true;
    api.pricing(currencyOverride === "USD" || currencyOverride === "INR" ? currencyOverride : "")
      .then((data) => { if (live) setPricing(data); })
      .catch(() => {
        if (live) {
          setPricing({
            currency: "INR",
            provider: "razorpay",
            payments_enabled: Boolean(sub?.payments_enabled),
            monthly_display: "₹29",
            yearly_display: "₹199",
            razorpay_enabled: Boolean(sub?.razorpay_enabled ?? sub?.payments_enabled),
            razorpay_intl_enabled: Boolean(sub?.razorpay_intl_enabled),
          });
        }
      });
    return () => { live = false; };
  }, [currencyOverride, sub?.payments_enabled, sub?.razorpay_enabled, sub?.razorpay_intl_enabled]);

  useEffect(() => {
    loadRazorpay().catch(() => {});
  }, []);

  useEffect(() => {
    document.title = "Purchase Premium · PyClips";
  }, []);

  useEffect(() => {
    if (premium) {
      setMsg("Premium is active. You can close this tab and return to PyClips.");
    }
  }, [premium]);

  async function buy(plan) {
    if (premium) return;
    const currency = pricing?.currency === "USD" ? "USD" : "INR";
    const enabled = currency === "USD"
      ? Boolean(pricing?.razorpay_intl_enabled ?? pricing?.payments_enabled)
      : Boolean(pricing?.razorpay_enabled ?? pricing?.payments_enabled ?? sub?.payments_enabled);
    if (!enabled) {
      setMsg(
        currency === "USD"
          ? "International USD plans are not configured yet. Enable Razorpay International, create USD plans, and set RAZORPAY_PLAN_MONTHLY_USD / YEARLY_USD."
          : "Razorpay is not configured on Railway yet. Add RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, and both INR plan ids, then redeploy."
      );
      return;
    }
    setBusy(true);
    setMsg("Opening Razorpay…");
    try {
      if (ticket) await api.bind(ticket).catch(() => {});
      const order = await api.subscribe(plan, ticket, currency);
      if (!order.key_id || !order.subscription_id) {
        throw new Error("Razorpay did not return a checkout session. Check plan ids in Railway Variables.");
      }
      await loadRazorpay();
      await new Promise((resolve, reject) => {
        const rzp = new window.Razorpay({
          key: order.key_id,
          subscription_id: order.subscription_id,
          name: order.name,
          description: order.description,
          prefill: order.prefill || {},
          theme: order.theme || { color: "#7C5CFF" },
          handler: async (res) => {
            try {
              const data = await api.verify({
                razorpay_payment_id: res.razorpay_payment_id,
                razorpay_subscription_id: res.razorpay_subscription_id,
                razorpay_signature: res.razorpay_signature,
                ticket,
              });
              if (data.user) setUser(data.user);
              setSub(data.subscription);
              setMsg("Premium is active. You can close this tab and return to PyClips.");
              resolve();
            } catch (err) {
              reject(err);
            }
          },
          modal: { ondismiss: () => reject(new Error("Payment cancelled.")) },
        });
        rzp.on("payment.failed", (resp) => reject(new Error(resp?.error?.description || "Payment failed.")));
        rzp.open();
      });
    } catch (err) {
      if (err.message !== "Payment cancelled.") setMsg(err.message || "Payment failed.");
      else setMsg("");
    } finally {
      setBusy(false);
    }
  }

  const monthlyPrice = pricing?.monthly_display || sub?.monthly_display || "₹29";
  const yearlyPrice = pricing?.yearly_display || sub?.yearly_display || "₹199";
  const isUsd = (pricing?.currency || sub?.currency) === "USD";
  const paymentsOk = isUsd
    ? Boolean(pricing?.razorpay_intl_enabled ?? pricing?.payments_enabled)
    : Boolean(pricing?.razorpay_enabled ?? pricing?.payments_enabled ?? sub?.payments_enabled);

  const currencyHref = `/pay?currency=${isUsd ? "INR" : "USD"}${ticket ? `&ticket=${encodeURIComponent(ticket)}` : ""}`;
  const monthlyHi = !premium && defaultPlan === "monthly";
  const yearlyHi = !premium && defaultPlan === "yearly";
  const monthlyActive = premium && billingPlan === "monthly";
  const yearlyActive = premium && billingPlan === "yearly";
  const statusOk = Boolean(msg) && msg.startsWith("Premium is active");
  const statusBusy = Boolean(msg) && msg.startsWith("Opening");

  return (
    <div className="pay-studio">
      <header className="pay-studio__nav">
        <BrandHome />
        <div className="pay-studio__email">
          <span className="pay-studio__dot" aria-hidden="true" />
          <span>{user.email}</span>
        </div>
      </header>

      <main className="pay-studio__main">
        <div className="pay-studio__inner">
          <h1>Purchase Premium</h1>
          <p className="pay-studio__lead">
            {isUsd
              ? "Autopay via Razorpay International (USD). Cancel anytime from Razorpay or your card issuer."
              : "Autopay via Razorpay (INR). Cancel anytime from Razorpay or your bank mandate."}
          </p>
          <a className="pay-studio__fx" href={currencyHref}>
            Show {isUsd ? "₹ INR" : "$ USD"} prices
          </a>

          {lockedEmail && user.email && lockedEmail !== user.email && (
            <p className="pay-studio__alert">
              This purchase was started in PyClips as <b>{lockedEmail}</b>. Log out and sign in with that email.
            </p>
          )}

          <div className="pay-studio__plans">
            <button
              type="button"
              className={
                "pay-studio__card"
                + (monthlyHi ? " is-hi" : "")
                + (premium ? " is-locked" : "")
                + (monthlyActive ? " is-current" : "")
              }
              disabled={busy || premium}
              onClick={() => buy("monthly")}
            >
              <div className="pay-studio__card-top">
                <span className="pay-studio__name">Monthly{monthlyActive ? " · active" : ""}</span>
                {monthlyHi ? <em>Selected</em> : null}
                {monthlyActive ? <em className="is-live">Active</em> : null}
              </div>
              <div className="pay-studio__price">
                <strong>{monthlyPrice}</strong>
                <small>/ month</small>
              </div>
              <div className="pay-studio__meta">
                <span>{premium ? "Unavailable" : busy ? "Please wait…" : "per month · autopay"}</span>
                <span className="pay-studio__go" aria-hidden="true">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </span>
              </div>
            </button>

            <button
              type="button"
              className={
                "pay-studio__card"
                + (yearlyHi ? " is-hi" : "")
                + (premium ? " is-locked" : "")
                + (yearlyActive ? " is-current" : "")
              }
              disabled={busy || premium}
              onClick={() => buy("yearly")}
            >
              <div className="pay-studio__card-top">
                <span className="pay-studio__name">Yearly{yearlyActive ? " · active" : ""}</span>
                {!isUsd && !yearlyActive ? <em className="is-gold">2 months free</em> : null}
                {yearlyActive ? <em className="is-live">Active</em> : null}
              </div>
              <div className="pay-studio__price">
                <strong>{yearlyPrice}</strong>
                <small>/ year</small>
              </div>
              <div className="pay-studio__meta">
                <span>
                  {premium
                    ? "Unavailable"
                    : busy
                      ? "Please wait…"
                      : isUsd
                        ? "per year · autopay"
                        : "per year · autopay · 2 months free"}
                </span>
                <span className="pay-studio__go" aria-hidden="true">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </span>
              </div>
            </button>
          </div>

          {msg ? (
            <p className={"pay-studio__status" + (statusOk ? " is-ok" : statusBusy ? " is-busy" : " is-err")}>{msg}</p>
          ) : (
            <p className="pay-studio__status" aria-hidden="true">&nbsp;</p>
          )}

          {!paymentsOk && (
            <p className="pay-studio__alert">
              {isUsd
                ? "International USD plans are not configured yet. Enable Razorpay International and set RAZORPAY_PLAN_MONTHLY_USD / YEARLY_USD."
                : "Razorpay is not configured on Railway yet. Add RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, and both INR plan ids, then redeploy."}
            </p>
          )}
        </div>
      </main>

      <footer className="pay-studio__foot">
        <span>© 2026 PyClips</span>
        <span aria-hidden="true">·</span>
        <a href="/privacy">Privacy</a>
      </footer>
    </div>
  );
}

function Admin() {
  const [gate, setGate] = useState("checking");
  const [tab, setTab] = useState("codes");
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

  async function loadAdmin() {
    const [couponData, downloadData] = await Promise.all([api.adminCoupons(), api.adminDownload()]);
    setCoupons(couponData.coupons || []);
    setStorage(couponData.storage || null);
    setDownloadMeta(downloadData);
    setDownloadUrl(downloadData.url || "");
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
      setTab("codes");
      setGate("login");
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
          <p className="landing-sub">Redeem codes and the Windows download link. Not a public account page.</p>
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

  return (
    <div className="page">
      <header className="top">
        <BrandHome />
        <SurfaceFrame variant="ghost" size="sm">
          <button type="button" className="btn btn-ghost" onClick={logout} disabled={busy}>Log out</button>
        </SurfaceFrame>
      </header>
      <nav className="admin-nav" aria-label="Admin">
        <SurfaceFrame variant={tab === "codes" ? "primary" : "ghost"} size="sm">
          <button type="button" className={tab === "codes" ? "btn btn-primary" : "btn btn-ghost"} onClick={() => { setTab("codes"); setMsg(""); }}>
            Redeem codes
          </button>
        </SurfaceFrame>
        <SurfaceFrame variant={tab === "download" ? "primary" : "ghost"} size="sm">
          <button type="button" className={tab === "download" ? "btn btn-primary" : "btn btn-ghost"} onClick={() => { setTab("download"); setMsg(""); }}>
            Download
          </button>
        </SurfaceFrame>
      </nav>
      {tab === "download" ? (
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
              {msg && <p className={msg.includes("live") ? "note ok" : "error"}>{msg}</p>}
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
      ) : (
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
          {msg && <p className="error">{msg}</p>}
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

export default function App() {
  const ticket = qs("ticket");
  const defaultPlan = qs("plan") === "yearly" ? "yearly" : "monthly";
  const page = pathOf();
  const isPrivacy = page === "/privacy";
  const isAdmin = page === "/admin";
  const isLanding = (page === "/" || page === "/landing") && !ticket;
  const needsAuthGate = !isLanding && !isPrivacy && !isAdmin;

  const [ready, setReady] = useState(!needsAuthGate);
  const [user, setUser] = useState(null);
  const [sub, setSub] = useState(null);
  const [lockedEmail, setLockedEmail] = useState("");

  useEffect(() => {
    if (isPrivacy || isAdmin) return undefined;
    let live = true;
    (async () => {
      try {
        if (ticket) {
          const peek = await api.peek(ticket).catch(() => null);
          if (live && peek?.email) setLockedEmail(peek.email);
        }
        const data = await api.me();
        if (!live) return;
        setUser(data.user || null);
        setSub(data.subscription || null);
        if (data.user && ticket) await api.bind(ticket).catch(() => {});
      } finally {
        if (live) setReady(true);
      }
    })();
    return () => { live = false; };
  }, [ticket, isPrivacy, isAdmin]);

  if (isPrivacy) {
    return <Privacy />;
  }
  if (isAdmin) {
    return <Admin />;
  }
  if (isLanding) {
    return <Landing user={user} />;
  }

  if (!ready) return <div className="boot">Loading…</div>;

  if (!user) {
    return (
      <AuthPanel
        ticket={ticket}
        lockedEmail={lockedEmail}
        footer={<LegalFooter />}
        onAuthed={(data) => {
          setUser(data.user);
          setSub(data.subscription);
          if (ticket && page !== "/pay") {
            window.history.replaceState({}, "", `/pay?ticket=${encodeURIComponent(ticket)}&plan=${defaultPlan}`);
          }
        }}
      />
    );
  }

  if (page === "/pay" || ticket) {
    return <Pay user={user} sub={sub} ticket={ticket} defaultPlan={defaultPlan} lockedEmail={lockedEmail} setSub={setSub} setUser={setUser} />;
  }
  return <Account user={user} sub={sub} setSub={setSub} setUser={setUser} />;
}
