import { useEffect, useState } from "react";
import { api } from "../api.js";
import AuthGateShell from "./auth/AuthGateShell.jsx";
import AuthStitchShowcase from "./auth/AuthStitchShowcase.jsx";

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path fill="#EA4335" d="M12 10.2v3.6h5.1c-.2 1.2-1.4 3.6-5.1 3.6-3.1 0-5.6-2.6-5.6-5.7S8.9 6 12 6c1.8 0 3 .7 3.7 1.4l2.5-2.4C16.7 3.6 14.6 2.7 12 2.7 6.9 2.7 2.8 6.8 2.8 11.7S6.9 20.7 12 20.7c5.2 0 8.6-3.6 8.6-8.7 0-.6-.1-1-.2-1.5H12z" />
      <path fill="#4285F4" d="M3.9 7.4l3 2.2C7.7 7.4 9.7 6 12 6c1.8 0 3 .7 3.7 1.4l2.5-2.4C16.7 3.6 14.6 2.7 12 2.7 8.2 2.7 4.9 4.8 3.9 7.4z" />
      <path fill="#34A853" d="M12 20.7c2.5 0 4.6-.8 6.1-2.2l-2.8-2.2c-.8.6-1.9 1-3.3 1-3.6 0-4.8-2.4-5.1-3.6l-3 2.3C5 18.6 8.1 20.7 12 20.7z" />
      <path fill="#FBBC05" d="M6.9 13.7c-.2-.6-.3-1.2-.3-1.9 0-.7.1-1.3.3-1.9l-3-2.3C3.3 9 3 10.3 3 11.8s.3 2.8.9 4.2l3-2.3z" />
    </svg>
  );
}

function MailIco() {
  return (
    <svg className="auth-field__ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="M3 7l9 7 9-7" />
    </svg>
  );
}

function LockIco() {
  return (
    <svg className="auth-field__ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function UserIco() {
  return (
    <svg className="auth-field__ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5 19c1.6-3.2 4-4.8 7-4.8S18.4 15.8 20 19" />
    </svg>
  );
}

function EyeIco({ off }) {
  return off ? (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M3 3l18 18" />
      <path d="M10.6 10.6A2 2 0 0 0 12 14a2 2 0 0 0 1.4-.6" />
      <path d="M9.9 5.1A10.6 10.6 0 0 1 12 5c5.5 0 9.5 4.5 10.5 7-0.4 1-1.2 2.4-2.5 3.7" />
      <path d="M6.1 6.1C4.2 7.5 2.8 9.3 1.5 12c1.1 2.6 5.1 7 10.5 7 1.5 0 2.9-.3 4.2-.8" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M1.5 12C2.6 9.4 6.6 5 12 5s9.4 4.4 10.5 7c-1.1 2.6-5.1 7-10.5 7S2.6 14.6 1.5 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function ArrowIco() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M5 12h14" />
      <path d="M13 6l6 6-6 6" />
    </svg>
  );
}

export default function AuthPanel({ ticket, lockedEmail, onAuthed, footer }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState(lockedEmail || "");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [googleOn, setGoogleOn] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("auth_error");
    if (q) {
      setError(q);
      const url = new URL(window.location.href);
      url.searchParams.delete("auth_error");
      window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    }
    api.providers().then((p) => setGoogleOn(Boolean(p.google))).catch(() => setGoogleOn(false));
  }, []);

  useEffect(() => {
    if (lockedEmail) setEmail(lockedEmail);
  }, [lockedEmail]);

  function startGoogle() {
    if (!googleOn) {
      setError("Google login is not set up on this website yet.");
      return;
    }
    const params = new URLSearchParams();
    if (ticket) params.set("ticket", ticket);
    if (lockedEmail || email) params.set("hint", lockedEmail || email.trim());
    window.location.href = `/api/auth/google?${params.toString()}`;
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      let data;
      if (mode === "signup") {
        try {
          data = await api.register(email.trim(), password, username.trim(), ticket);
        } catch (err) {
          if (err.status === 409) {
            data = await api.login(email.trim(), password, ticket);
          } else {
            throw err;
          }
        }
      } else {
        data = await api.login(email.trim(), password, ticket);
      }
      if (!data.user) throw new Error("Could not sign in.");
      onAuthed(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const panel = (
    <>
      <div className="auth-gate__head">
        <p className="auth-gate__kicker">pyclips.in</p>
        <h1>{mode === "signup" ? "Create your PyClips account" : "Sign in to PyClips"}</h1>
        <p>
          {mode === "signup"
            ? "Premium billing and coupons are managed here, then sync to the desktop app."
            : "Access Premium, redeem codes, and manage your subscription."}
        </p>
      </div>

      <div className="auth-gate__tabs" role="tablist" aria-label="Account mode">
        <button
          type="button"
          className={"auth-gate__tab" + (mode === "login" ? " active" : "")}
          onClick={() => { setMode("login"); setError(""); }}
        >
          Sign in
        </button>
        <button
          type="button"
          className={"auth-gate__tab" + (mode === "signup" ? " active" : "")}
          onClick={() => { setMode("signup"); setError(""); }}
        >
          Create account
        </button>
      </div>

      <div className="auth-gate__oauth">
        <button type="button" className="btn auth-oauth" onClick={startGoogle} disabled={busy}>
          <GoogleMark /> Continue with Google
        </button>
      </div>

      <div className="auth-gate__divider">Email</div>

      <form className="auth-gate__form auth-form" onSubmit={submit}>
        {mode === "signup" && (
          <label className="auth-label">
            Username
            <span className="auth-field">
              <UserIco />
              <input
                className="auth-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="yourname"
                minLength={3}
                maxLength={24}
              />
            </span>
          </label>
        )}
        <label className="auth-label">
          Email
          <span className="auth-field">
            <MailIco />
            <input
              className="auth-input"
              type="email"
              required
              value={email}
              readOnly={Boolean(lockedEmail)}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@email.com"
            />
          </span>
        </label>
        <label className="auth-label">
          Password
          <span className="auth-field">
            <LockIco />
            <input
              className="auth-input"
              type={showPassword ? "text" : "password"}
              required
              minLength={mode === "signup" ? 8 : 1}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "signup" ? "At least 8 characters" : "Your password"}
            />
            <button
              type="button"
              className="auth-field__eye"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((v) => !v)}
            >
              <EyeIco off={showPassword} />
            </button>
          </span>
        </label>
        {error ? <div className="error">{error}</div> : null}
        <button className="btn btn-primary auth-submit auth-gate__submit" type="submit" disabled={busy}>
          {busy ? "Please wait…" : mode === "signup" ? "Create account" : "Sign in"}
          {!busy ? <ArrowIco /> : null}
        </button>
      </form>
    </>
  );

  return (
    <div className="auth-gate-page">
      <AuthGateShell
        showcase={<AuthStitchShowcase variant="web" />}
        panel={panel}
        footer={footer}
      />
    </div>
  );
}
