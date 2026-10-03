import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import SurfaceFrame from "../components/SurfaceFrame.jsx";
import BrandLogo from "../components/BrandLogo.jsx";
import {
  DOWNLOAD_URL,
  MICROSOFT_STORE_URL,
  SHOW_ACCOUNT_BUTTON,
  SHOW_DOWNLOAD_SECTION,
  SHOW_FINAL_CTA,
  SHOW_HERO_DOWNLOAD,
  SHOW_HERO_STORE,
  SHOW_PRICING_PANEL,
  SOCIALS,
  SYSTEME_LIFETIME_URL,
  SYSTEME_MONTHLY_URL,
  checkoutUrl,
} from "../siteConfig.js";

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function easeOutQuint(t) {
  return 1 - (1 - t) ** 5;
}

function Bolt({ size = 22 }) {
  return <BrandLogo size={size} />;
}

function MicrosoftMark({ size = 18 }) {
  return (
    <svg className="ms-mark" viewBox="0 0 23 23" width={size} height={size} aria-hidden="true">
      <rect width="11" height="11" fill="#F25022" />
      <rect x="12" width="11" height="11" fill="#7FBA00" />
      <rect y="12" width="11" height="11" fill="#00A4EF" />
      <rect x="12" y="12" width="11" height="11" fill="#FFB900" />
    </svg>
  );
}

function WindowsMark({ size = 18 }) {
  return (
    <svg className="os-mark" viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden="true">
      <path d="M2 4.3 10 3.2v7.7H2zM11 3.1 22 1.5v9.4H11zM2 12h8v7.8L2 18.7zM11 12h11v9.5L11 20z" />
    </svg>
  );
}

function AppleMark({ size = 18 }) {
  return (
    <svg className="os-mark" viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden="true">
      <path d="M16.37 12.6c-.02-2.3 1.88-3.4 1.96-3.46-1.07-1.56-2.73-1.78-3.32-1.8-1.41-.14-2.76.83-3.48.83-.72 0-1.82-.81-3-.79-1.54.02-2.96.9-3.76 2.28-1.6 2.78-.41 6.9 1.15 9.16.76 1.1 1.67 2.34 2.86 2.3 1.15-.05 1.58-.74 2.97-.74 1.38 0 1.77.74 2.98.72 1.23-.02 2.01-1.12 2.77-2.23.87-1.28 1.23-2.52 1.25-2.58-.03-.01-2.4-.92-2.38-3.69zM14.1 5.84c.63-.77 1.06-1.83.94-2.89-.91.04-2.01.61-2.66 1.37-.58.67-1.1 1.76-.96 2.8 1.01.08 2.05-.52 2.68-1.28z" />
    </svg>
  );
}

function storeLabel(className, children) {
  if (!(className || "").includes("landing-btn-store")) return children;
  return (
    <>
      <MicrosoftMark size={(className || "").includes("landing-btn-lg") ? 20 : 16} />
      <span>{children}</span>
    </>
  );
}

function glowFromClass(className) {
  const raw = className || "";
  const variant = raw.includes("landing-btn-store") ? "store" : raw.includes("landing-btn-ghost") ? "ghost" : "primary";
  const size = raw.includes("landing-btn-lg") ? "lg" : "md";
  const full = raw.includes("landing-btn-full");
  return { variant, size, full };
}

function ExternalCta({ url, className, children }) {
  const glow = glowFromClass(className);
  const label = storeLabel(className, children);
  const inner = !url ? (
    <button type="button" className={`${className} is-disabled`} disabled>
      {label}
      <span className="landing-soon">Coming soon</span>
    </button>
  ) : /^https?:\/\//i.test(url) ? (
    <a className={className} href={url} target="_blank" rel="noopener noreferrer">
      {label}
    </a>
  ) : (
    <a className={className} href={url} rel="noreferrer">
      {label}
    </a>
  );
  return (
    <SurfaceFrame variant={glow.variant} size={glow.size} full={glow.full}>
      {inner}
    </SurfaceFrame>
  );
}

function Shot({ src, alt, eager = false }) {
  return (
    <figure className="landing-shot">
      <div className="landing-shot-bar" aria-hidden="true">
        <i /><i /><i />
        <span>Product shot</span>
      </div>
      <img src={src} alt={alt} width="1280" height="700" loading={eager ? "eager" : "lazy"} decoding="async" />
    </figure>
  );
}

const FAQS = [
  {
    q: "What is PyClips?",
    a: "PyClips is a desktop app for Windows and Mac that turns videos into captioned short-form clips. Import, set up the clip, pick a soundtrack, style captions, then bake and export MP4s.",
  },
  {
    q: "How do I install PyClips?",
    a: "Get PyClips from the Microsoft Store on Windows 10 or Windows 11. A direct Windows installer is also offered on this site when it is available. On Mac, PyClips runs on macOS 14 Sonoma or newer, on Apple Silicon and Intel Macs: open the .dmg, drag PyClips to Applications, and approve it once in System Settings ? Privacy & Security.",
  },
  {
    q: "Can I use my own videos?",
    a: "Yes. Drop in a video file, or paste a supported YouTube link where that path is enabled in the app.",
  },
  {
    q: "Does PyClips support vertical videos?",
    a: "Yes. You can output 9:16 vertical, 16:9 landscape, or 1:1 square, with Style controls and keyframes when you want precise framing.",
  },
  {
    q: "Can I customize captions?",
    a: "Yes. PyClips includes caption presets, plus typography, highlighting, position, and custom styles.",
  },
  {
    q: "Does PyClips use my GPU?",
    a: "On Windows, when a compatible NVIDIA GPU is available, PyClips can use GPU acceleration for processing. CPU processing remains available otherwise. On Mac, PyClips processes on the CPU.",
  },
  {
    q: "Where are my exported clips saved?",
    a: "On Windows, finished clips are saved to your PyClips Downloads folder. On Mac, they go to Movies → PyClips.",
  },
  {
    q: "Is there a free version?",
    a: "Yes. Free accounts can bake 20 clips lifetime. Deleting a clip does not restore a slot.",
  },
  {
    q: "How does Premium work?",
    a: "Premium is purchased on this website through Razorpay. India pays in INR (₹99 / month or ₹599 / year). Outside India, Razorpay International charges in USD ($2.99 / month or $29.99 / year). It unlocks unlimited bakes and premium features in the desktop app after you sign in with the same account.",
  },
  {
    q: "Can I use PyClips without Premium?",
    a: "Yes. You can use PyClips on the free tier, up to the 20-clip lifetime limit.",
  },
];

function currencyFromQuery() {
  const value = (new URLSearchParams(window.location.search).get("currency") || "").toUpperCase();
  return value === "USD" || value === "INR" ? value : "";
}

export default function Landing({ user }) {
  const pageRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [exeUrl, setExeUrl] = useState(DOWNLOAD_URL || "");
  const [pricing, setPricing] = useState(null);
  const currencyOverride = currencyFromQuery();

  useEffect(() => {
    document.title = "PyClips — Turn Any Video Into Captioned Shorts";
  }, []);

  useEffect(() => {
    let live = true;
    api.pricing(currencyOverride)
      .then((data) => { if (live) setPricing(data); })
      .catch(() => {
        if (!live) return;
        setPricing(
          currencyOverride === "USD"
            ? { currency: "USD", monthly_display: "$2.99", yearly_display: "$29.99" }
            : { currency: "INR", monthly_display: "₹99", yearly_display: "₹599" },
        );
      });
    return () => { live = false; };
  }, [currencyOverride]);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const data = await api.publicDownload();
        if (!live) return;
        if (data && data.available) setExeUrl("/download");
      } catch {
        /* keep siteConfig / empty */
      }
    })();
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  useEffect(() => {
    const root = pageRef.current;
    if (!root) return undefined;
    const reduced = prefersReducedMotion();
    const reveals = root.querySelectorAll(".reveal");
    let io;
    if (reduced || typeof IntersectionObserver === "undefined") {
      reveals.forEach((el) => el.classList.add("is-in"));
    } else {
      io = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            entry.target.classList.add("is-in");
            io.unobserve(entry.target);
          }
        },
        { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
      );
      reveals.forEach((el) => io.observe(el));
    }

    let frame = 0;
    const cancelScroll = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
    };

    const navOffset = () => {
      const nav = root.querySelector(".landing-nav");
      return (nav ? nav.getBoundingClientRect().height : 64) + 12;
    };

    const yForId = (id) => {
      const el = document.getElementById(id);
      if (!el) return null;
      el.classList.add("is-in");
      let top = 0;
      for (let node = el; node; node = node.offsetParent) top += node.offsetTop;
      return Math.max(0, top - navOffset());
    };

    const jumpTo = (y) => {
      window.scrollTo({ top: y, left: 0, behavior: "auto" });
    };

    const animateTo = (y) => {
      cancelScroll();
      const startY = window.scrollY;
      const dist = y - startY;
      if (Math.abs(dist) < 2 || reduced) {
        jumpTo(y);
        return;
      }
      const duration = Math.min(900, Math.max(480, Math.abs(dist) * 0.42));
      const t0 = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - t0) / duration);
        jumpTo(startY + dist * easeOutQuint(t));
        if (t < 1) frame = requestAnimationFrame(step);
        else frame = 0;
      };
      frame = requestAnimationFrame(step);
    };

    const goToHash = (id, push) => {
      const y = id ? yForId(id) : 0;
      if (y == null) return false;
      if (push && window.location.hash !== `#${id}`) {
        history.pushState(null, "", `#${id}`);
      }
      animateTo(y);
      return true;
    };

    const onClick = (e) => {
      const a = e.target.closest("a[href^='#']");
      if (!a || !root.contains(a)) return;
      const id = decodeURIComponent((a.getAttribute("href") || "").slice(1));
      if (!id || !document.getElementById(id)) return;
      e.preventDefault();
      const drawerOpen = Boolean(root.querySelector(".landing-drawer"));
      setMenuOpen(false);
      const run = () => goToHash(id, true);
      if (drawerOpen) requestAnimationFrame(() => requestAnimationFrame(run));
      else run();
    };

    const onPop = () => {
      const id = decodeURIComponent(window.location.hash.replace(/^#/, ""));
      if (!id) animateTo(0);
      else goToHash(id, false);
    };

    const onUserInterrupt = (e) => {
      if (e.type === "keydown") {
        const keys = ["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "];
        if (!keys.includes(e.key)) return;
      }
      cancelScroll();
    };

    root.addEventListener("click", onClick);
    window.addEventListener("popstate", onPop);
    window.addEventListener("wheel", onUserInterrupt, { passive: true });
    window.addEventListener("touchstart", onUserInterrupt, { passive: true });
    window.addEventListener("keydown", onUserInterrupt);

    const initial = decodeURIComponent(window.location.hash.replace(/^#/, ""));
    if (initial) {
      requestAnimationFrame(() => goToHash(initial, false));
    }

    return () => {
      cancelScroll();
      io?.disconnect();
      root.removeEventListener("click", onClick);
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("wheel", onUserInterrupt);
      window.removeEventListener("touchstart", onUserInterrupt);
      window.removeEventListener("keydown", onUserInterrupt);
    };
  }, []);

  function closeMenu() {
    setMenuOpen(false);
  }

  const isUsd = (pricing?.currency || currencyOverride) === "USD";
  const monthlyPrice = pricing?.monthly_display || (isUsd ? "$2.99" : "₹99");
  const yearlyPrice = pricing?.yearly_display || (isUsd ? "$29.99" : "₹599");
  const currencyHref = `/?currency=${isUsd ? "INR" : "USD"}#pricing`;
  const payHref = `/pay?currency=${isUsd ? "USD" : "INR"}`;
  const getHref = SHOW_DOWNLOAD_SECTION ? "#download" : "#get";

  return (
    <div className="landing landing-stitch" ref={pageRef}>
      <header className="landing-nav">
        <a className="landing-brand" href="/">
          <span className="landing-mark"><Bolt size={20} /></span>
          PyClips
        </a>
        <nav className="landing-nav-links" aria-label="Page">
          <a href="#product">Product</a>
          <a href="#features">Features</a>
          {SHOW_PRICING_PANEL && <a href="#pricing">Pricing</a>}
          {SHOW_DOWNLOAD_SECTION && <a href="#download">Download</a>}
        </nav>
        <div className="landing-nav-actions">
          {SHOW_ACCOUNT_BUTTON && (user ? (
            <SurfaceFrame variant="ghost" size="sm">
              <a className="landing-btn landing-btn-ghost" href="/account">Account</a>
            </SurfaceFrame>
          ) : (
            <SurfaceFrame variant="ghost" size="sm">
              <a className="landing-btn landing-btn-ghost" href="/login">Log in</a>
            </SurfaceFrame>
          ))}
          <SurfaceFrame variant="primary" size="sm">
            <a className="landing-btn landing-btn-primary" href={getHref}>Get PyClips</a>
          </SurfaceFrame>
          <button
            type="button"
            className="landing-burger"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <span /><span /><span />
          </button>
        </div>
      </header>

      {menuOpen && (
        <div className="landing-drawer" role="dialog" aria-label="Menu">
          <a href="#product" onClick={closeMenu}>Product</a>
          <a href="#features" onClick={closeMenu}>Features</a>
          {SHOW_PRICING_PANEL && <a href="#pricing" onClick={closeMenu}>Pricing</a>}
          {SHOW_DOWNLOAD_SECTION && <a href="#download" onClick={closeMenu}>Download</a>}
          {SHOW_ACCOUNT_BUTTON && (user ? (
            <a href="/account" onClick={closeMenu}>Account</a>
          ) : (
            <a href="/login" onClick={closeMenu}>Log in</a>
          ))}
          <SurfaceFrame variant="primary" full>
            <a className="landing-btn landing-btn-primary" href={getHref} onClick={closeMenu}>Get PyClips</a>
          </SurfaceFrame>
        </div>
      )}

      <main>
        <section className="landing-hero" id="get">
          <p className="landing-eyebrow">Desktop clip studio for Windows &amp; Mac</p>
          <h1>
            Turn long videos into
            <br />
            <span>captioned vertical clips.</span>
          </h1>
          <p className="landing-lead">
            Import a video, set up the clip, add a soundtrack,
            style captions, then bake and export shorts ready to post.
          </p>
          <div className="landing-hero-ctas">
            {SHOW_HERO_DOWNLOAD && (
              <ExternalCta url={exeUrl} className="landing-btn landing-btn-primary landing-btn-lg">
                Download PyClips
              </ExternalCta>
            )}
            {SHOW_HERO_STORE && (
              <ExternalCta url={MICROSOFT_STORE_URL} className="landing-btn landing-btn-store landing-btn-lg">
                Microsoft Store
              </ExternalCta>
            )}
            <ExternalCta url={checkoutUrl(SYSTEME_MONTHLY_URL)} className="landing-btn landing-btn-primary landing-btn-lg">
              <WindowsMark /><span>PyClips Monthly</span>
            </ExternalCta>
            <ExternalCta url={checkoutUrl(SYSTEME_LIFETIME_URL)} className="landing-btn landing-btn-primary landing-btn-lg">
              <WindowsMark /><span>PyClips Lifetime</span>
            </ExternalCta>
            <ExternalCta url={checkoutUrl(SYSTEME_MONTHLY_URL)} className="landing-btn landing-btn-primary landing-btn-lg">
              <AppleMark /><span>Mac Monthly</span>
            </ExternalCta>
            <ExternalCta url={checkoutUrl(SYSTEME_LIFETIME_URL)} className="landing-btn landing-btn-primary landing-btn-lg">
              <AppleMark /><span>Mac Lifetime</span>
            </ExternalCta>
          </div>
          <ul className="landing-trust" aria-label="Product highlights">
            <li>Windows &amp; Mac</li>
            <li>Styled captions</li>
            <li>GPU optional</li>
          </ul>
          <div className="landing-hero-visual">
            <Shot
              src="/screenshots/dashboard.webp"
              alt="PyClips dashboard with 9:16 preview, caption presets, and GPU processing"
              eager
            />
          </div>
        </section>

        <section className="landing-strip reveal" aria-label="Highlights">
          <h2>Built for creators.</h2>
          <ul className="landing-pills">
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
              </svg>
              Caption presets
            </li>
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
              Style & framing
            </li>
            <li>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
              </svg>
              Soundtrack ducking
            </li>
          </ul>
        </section>

        <section className="landing-block reveal" id="product">
          <h2>From raw video to ready-to-post short.</h2>
          <p className="landing-subhead">PyClips handles the repetitive editing work so you can focus on the content.</p>
          <div className="landing-stages">
            <article>
              <div className="landing-stage-top">
                <span>01</span>
                <em>Source</em>
              </div>
              <h3>Import</h3>
              <p>Drop in a video or paste a supported link.</p>
              <Shot src="/screenshots/create.webp" alt="PyClips create screen with upload and paste-link bar" />
            </article>
            <article>
              <div className="landing-stage-top">
                <span>02</span>
                <em>Customization</em>
              </div>
              <h3>Style</h3>
              <p>Clip setup, soundtrack, captions, and look — in the same order as the app.</p>
              <Shot src="/screenshots/captions.webp" alt="PyClips caption style picker beside a phone preview" />
            </article>
            <article>
              <div className="landing-stage-top">
                <span>03</span>
                <em>Output</em>
              </div>
              <h3>Export</h3>
              <p>Bake and export a polished short ready to post.</p>
              <Shot src="/screenshots/library.webp" alt="PyClips library with a finished vertical clip" />
            </article>
          </div>
        </section>

        <section className="landing-split reveal" id="features">
          <div>
            <p className="landing-kicker">Captions</p>
            <h2>Captions that look like they belong on your feed.</h2>
            <p>
              Choose from a growing library of short-form caption styles, then customize them to match your content.
            </p>
            <ul className="landing-feature-list">
              <li>Trending styles</li>
              <li>Custom typography</li>
              <li>Word highlighting</li>
              <li>Position control</li>
              <li>Caption presets</li>
            </ul>
          </div>
          <Shot src="/screenshots/captions.webp" alt="Caption themes and word highlighting on the preview" />
        </section>

        <section className="landing-split landing-split-rev reveal">
          <div>
            <p className="landing-kicker">Style</p>
            <h2>Turn landscape footage into vertical content.</h2>
            <p>
              Style your footage for 9:16, 16:9 or 1:1 without manually rebuilding every shot.
            </p>
            <ul className="landing-ratios">
              <li>9:16 Vertical</li>
              <li>16:9 Landscape</li>
              <li>1:1 Square</li>
            </ul>
            <p className="landing-note">Keyframe framing in Style when you want precise control.</p>
          </div>
          <Shot src="/screenshots/dashboard.webp" alt="Aspect ratio controls set to 9:16 with a vertical phone preview" />
        </section>

        <section className="landing-split reveal">
          <div>
            <p className="landing-kicker">Soundtrack</p>
            <h2>Give every clip more energy.</h2>
            <p>
              Pick a soundtrack, control volume, duck under speech, and line tracks up with the beat.
            </p>
            <ul className="landing-feature-list">
              <li>Soundtrack waveform</li>
              <li>Volume</li>
              <li>Ducking</li>
              <li>Beat analysis</li>
            </ul>
          </div>
          <Shot src="/screenshots/add.webp" alt="PyClips editor with clip preview and workflow steps" />
        </section>

        <section className="landing-block landing-flow-block reveal">
          <h2>One workflow. No editing headache.</h2>
          <p className="landing-subhead">Import, clip setup, soundtrack, captions, style, review, and export from one desktop app on Windows or Mac.</p>
          <ol className="landing-flow">
            <li>Import</li>
            <li>Clip</li>
            <li>Soundtrack</li>
            <li>Captions</li>
            <li>Style</li>
            <li>Review</li>
            <li>Export</li>
          </ol>
        </section>

        {SHOW_PRICING_PANEL && (
        <section className="landing-block reveal" id="pricing">
          <h2>Start creating with PyClips.</h2>
          <p className="landing-subhead">
            {isUsd
              ? `${monthlyPrice} / month or ${yearlyPrice} / year · Razorpay International (USD).`
              : `${monthlyPrice} / month or ${yearlyPrice} / year · Razorpay (INR).`}
          </p>
          <a className="landing-fx" href={currencyHref}>
            Show {isUsd ? "₹ INR" : "$ USD"} prices
          </a>
          <div className="landing-plans">
            <article className="landing-plan">
              <div className="landing-plan-head">
                <p className="landing-plan-name">Free</p>
                <em>Starter</em>
              </div>
              <p className="landing-plan-price">{isUsd ? "$0" : "₹0"}</p>
              <p className="landing-plan-meta">20 lifetime baked clips</p>
              <ul>
                <li>Caption presets</li>
                <li>Basic editing</li>
                <li>GPU acceleration</li>
              </ul>
              <p className="landing-note">Deleting a clip does not restore a slot.</p>
              <ExternalCta url={exeUrl} className="landing-btn landing-btn-ghost landing-btn-full">
                Download PyClips
              </ExternalCta>
            </article>
            <article className="landing-plan landing-plan-hi">
              <div className="landing-plan-head">
                <p className="landing-plan-name">Premium</p>
                <em>Premium</em>
              </div>
              <p className="landing-plan-price">{monthlyPrice} <small>/ month</small></p>
              <p className="landing-plan-meta">or {yearlyPrice} / year</p>
              <ul>
                <li>Unlimited bakes</li>
                <li>All caption styles</li>
                <li>Advanced features</li>
                <li>Premium features</li>
              </ul>
              <SurfaceFrame variant="primary" full>
                <a className="landing-btn landing-btn-primary landing-btn-full" href={payHref}>Get Premium</a>
              </SurfaceFrame>
              <p className="landing-note">
                {isUsd
                  ? "Billed on this website via Razorpay International. Cancel autopay from Razorpay or your card issuer."
                  : "Billed on this website via Razorpay. Cancel autopay from Razorpay or your bank mandate."}
              </p>
            </article>
          </div>
        </section>
        )}

        {SHOW_DOWNLOAD_SECTION && (
        <section className="landing-block landing-dl-block reveal" id="download">
          <h2>Get PyClips on Windows.</h2>
          <p className="landing-meta">Windows 10 / Windows 11</p>
          <div className="landing-dl">
            <article>
              <span className="landing-dl-ico" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </span>
              <h3>Direct download</h3>
              <p>{exeUrl ? "Windows installer (.exe). Click to start the download." : "The Windows installer will be available here when it is released."}</p>
              <ExternalCta url={exeUrl} className="landing-btn landing-btn-primary">
                Download PyClips
              </ExternalCta>
            </article>
            <article>
              <span className="landing-dl-ico landing-dl-ico-ms" aria-hidden="true">
                <MicrosoftMark size={18} />
              </span>
              <h3>Microsoft Store</h3>
              <p>Install PyClips from the Microsoft Store on Windows 10 and Windows 11.</p>
              <ExternalCta url={MICROSOFT_STORE_URL} className="landing-btn landing-btn-store">
                Microsoft Store
              </ExternalCta>
            </article>
          </div>
        </section>
        )}

        <section className="landing-block landing-faq-block reveal" id="faq">
          <h2>Frequently asked questions</h2>
          <p className="landing-subhead">How PyClips works on Windows and Mac, billing, and the free tier.</p>
          <div className="landing-faq">
            {FAQS.map((item) => (
              <details key={item.q} className="landing-faq-item">
                <summary>{item.q}</summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        {SHOW_FINAL_CTA && (
        <section className="landing-final reveal">
          <h2>Your next short is waiting.</h2>
          <p>Turn your long-form videos into polished short-form content with PyClips.</p>
          <div className="landing-hero-ctas">
            <ExternalCta url={exeUrl} className="landing-btn landing-btn-primary landing-btn-lg">
              Download PyClips
            </ExternalCta>
            <ExternalCta url={MICROSOFT_STORE_URL} className="landing-btn landing-btn-store landing-btn-lg">
              Microsoft Store
            </ExternalCta>
          </div>
        </section>
        )}
      </main>

      <footer className="landing-foot">
        <div className="landing-foot-brand">
          <span className="landing-mark sm"><Bolt size={16} /></span>
          <div>
            <strong>PyClips</strong>
            <p>AI-powered video clipping for Windows and Mac.</p>
          </div>
        </div>
        <nav aria-label="Footer">
          <a href="#product">Product</a>
          <a href="#features">Features</a>
          {SHOW_PRICING_PANEL && <a href="#pricing">Pricing</a>}
          {SHOW_DOWNLOAD_SECTION && <a href="#download">Download</a>}
          <a href="/privacy">Privacy</a>
          <a href="/login">Login</a>
        </nav>
        <div className="landing-social">
          {SOCIALS.map((s) => (
            <a key={s.label} href={s.href} target="_blank" rel="noreferrer">{s.label}</a>
          ))}
        </div>
        <p className="landing-copy">© 2026 PyClips. All rights reserved. <span>pyclips.in</span></p>
      </footer>
    </div>
  );
}
