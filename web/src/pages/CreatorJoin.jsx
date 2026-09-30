import { useEffect, useState } from "react";
import { api } from "../api.js";
import SurfaceFrame from "../components/SurfaceFrame.jsx";
import BrandLogo from "../components/BrandLogo.jsx";

function param(name) {
  const value = new URLSearchParams(window.location.search).get(name) || "";
  return /^(\{.*\}|%.*%)$/.test(value.trim()) ? "" : value.trim();
}

/** Accepts the bare affiliate ID or a whole affiliate link pasted from systeme.io. */
function affiliateCodeFrom(text) {
  const raw = (text || "").trim();
  const inLink = raw.match(/[?&]sa=([A-Za-z0-9_-]+)/);
  return inLink ? inLink[1] : raw;
}

export default function CreatorJoin() {
  const linkCode = param("sa");
  const [codeInput, setCodeInput] = useState(linkCode);
  const [name, setName] = useState(param("name"));
  const [email, setEmail] = useState(param("email"));
  const [payTo, setPayTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [copied, setCopied] = useState(false);
  const code = affiliateCodeFrom(codeInput);
  const shareLink = `${window.location.origin}/?sa=${encodeURIComponent(code)}`;

  useEffect(() => { document.title = "Creator payouts · PyClips"; }, []);

  async function submit(e) {
    e.preventDefault();
    if (!/^[A-Za-z0-9_-]{2,80}$/.test(code)) {
      setError("That doesn't look like a systeme.io affiliate ID. It starts with \"sa\", e.g. sa0282807757ee2b…");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.creatorJoin({ affiliate_code: code, name: name.trim(), email: email.trim(), pay_to: payTo.trim() });
      setDone(true);
    } catch (err) {
      setError(err.message || "Something went wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <a className="brand-hero" href="/" aria-label="PyClips home">
        <span className="brand-mark"><BrandLogo size={90} /></span>
        <span className="brand-word">PyClips</span>
      </a>
      <div className="auth-card">
        <h1 className="landing-title" style={{ fontSize: 24 }}>Get paid for your sales</h1>
        {done ? (
          <>
            <p className="note ok">
              You're set, {name.trim() || "creator"}. You get 40% of every sale from your link, renewals included, paid weekly to the UPI you entered.
            </p>
            <label className="auth-label">Share this link so every sale is counted for you
              <input className="auth-input" value={shareLink} readOnly onFocus={(e) => e.target.select()} />
            </label>
            <SurfaceFrame variant="primary" full>
              <button type="button" className="btn btn-primary auth-submit"
                onClick={() => navigator.clipboard.writeText(shareLink).then(() => setCopied(true))}>
                {copied ? "Copied" : "Copy link"}
              </button>
            </SurfaceFrame>
          </>
        ) : (
          <>
            <p className="landing-sub">You get 40% of every PyClips sale from your link, renewals included, paid weekly. Tell us where to send it.</p>
            <form className="auth-form" onSubmit={submit}>
              <label className="auth-label">Your affiliate ID
                <input className="auth-input" value={codeInput} readOnly={Boolean(linkCode)} required
                  onChange={(e) => setCodeInput(e.target.value)} placeholder="sa0282807757ee2b…" />
              </label>
              {!linkCode && (
                <p className="note">
                  Find it in your systeme.io affiliate dashboard under "Your affiliate ID", or in your welcome email.
                  You can also paste your whole affiliate link.
                </p>
              )}
              <label className="auth-label">Your name
                <input className="auth-input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} autoComplete="name" />
              </label>
              <label className="auth-label">Email
                <input className="auth-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={254} autoComplete="email" />
              </label>
              <label className="auth-label">UPI ID for payouts
                <input className="auth-input" value={payTo} onChange={(e) => setPayTo(e.target.value)} required minLength={3} maxLength={200} placeholder="name@upi" />
              </label>
              {error && <p className="error">{error}</p>}
              <SurfaceFrame variant="primary" full>
                <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>{busy ? "Please wait…" : "Save"}</button>
              </SurfaceFrame>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
