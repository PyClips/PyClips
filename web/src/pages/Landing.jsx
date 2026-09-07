import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import SurfaceFrame from "../components/SurfaceFrame.jsx";
import BrandLogo from "../components/BrandLogo.jsx";
import { DOWNLOAD_URL, MICROSOFT_STORE_URL, SOCIALS } from "../siteConfig.js";

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
      </div>
      <img src={src} alt={alt} width="1280" height="700" loading={eager ? "eager" : "lazy"} decoding="async" />
    </figure>
  );
}

const FAQS = [
  {
    q: "What is PyClips?",
    a: "PyClips is a Windows desktop app that turns videos into captioned short-form clips. It finds moments, burns styled captions, reframes for social sizes, and exports MP4s.",
  },
  {
    q: "How do I install PyClips?",
    a: "Get PyClips from the Microsoft Store on Windows 10 or Windows 11. A direct Windows installer is also offered on this site when it is available.",
  },
  {
    q: "Can I use my own videos?",
    a: "Yes. Drop in a video file, or paste a supported YouTube link where that path is enabled in the app.",
  },
  {
    q: "Does PyClips support vertical videos?",
    a: "Yes. You can output 9:16 vertical, 16:9 landscape, or 1:1 square, with manual reframing and keyframes when you want precise control.",
  },
  {
    q: "Can I customize captions?",
    a: "Yes. PyClips includes a library of short-form caption styles, plus typography, highlighting, position, and presets.",
  },
  {
    q: "Does PyClips use my GPU?",
    a: "When a compatible NVIDIA GPU is available, PyClips can use GPU acceleration for processing. CPU processing remains available otherwise.",
  },
  {
    q: "Where are my exported clips saved?",
    a: "Finished clips are saved to your PyClips Downloads folder.",
  },
  {
    q: "Is there a free version?",
    a: "Yes. Free accounts can generate 10 clips lifetime. Deleting a clip does not restore a slot.",
  },
  {
    q: "How does Premium work?",
    a: "Premium is purchased on this website through Razorpay. India pays in INR (₹19 / month or ₹199 / year). Outside India, Razorpay International charges in USD ($2.99 / month or $29.99 / year). It unlocks unlimited generations and premium features in the desktop app after you sign in with the same account.",
  },
  {
    q: "Can I use PyClips without Premium?",
    a: "Yes. You can use PyClips on the free tier, up to the 10-clip lifetime limit.",
  },
];

export default function Landing({ user }) {
  const pageRef = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [exeUrl, setExeUrl] = useState(DOWNLOAD_URL || "");
  const [pricing, setPricing] = useState(null);

  useEffect(() => {
    document.title = "PyClips — Turn Any Video Into Captioned Shorts";
  }, []);

  useEffect(() => {
    let live = true;
    api.pricing()
      .then((data) => { if (live) setPricing(data); })
      .catch(() => {});
    return () => { live = false; };
  }, []);

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

  return (
    <div className="landing" ref={pageRef}>
      <header className="landing-nav">
        <a className="landing-brand" href="/">
          <span className="landing-mark"><Bolt size={20} /></span>
          PyClips
        </a>
        <nav className="landing-nav-links" aria-label="Page">
          <a href="#product">Product</a>
          <a href="#features">Features</a>
          <a href="#pricing">Pricing</a>
          <a href="#download">Download</a>
        </nav>
        <div className="landing-nav-actions">
          {user ? (
            <SurfaceFrame variant="ghost" size="sm">
              <a className="landing-btn landing-btn-ghost" href="/account">Account</a>
            </SurfaceFrame>
          ) : (
            <SurfaceFrame variant="ghost" size="sm">
              <a className="landing-btn landing-btn-ghost" href="/login">Log in</a>
            </SurfaceFrame>
          )}
          <SurfaceFrame variant="primary" size="sm">
            <a className="landing-btn landing-btn-primary" href="#download">Get PyClips</a>
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
          <a href="#pricing" onClick={closeMenu}>Pricing</a>
          <a href="#download" onClick={closeMenu}>Download</a>
          {user ? (
            <a href="/account" onClick={closeMenu}>Account</a>
          ) : (
            <a href="/login" onClick={closeMenu}>Log in</a>
          )}
          <SurfaceFrame variant="primary" full>
            <a className="landing-btn landing-btn-primary" href="#download" onClick={closeMenu}>Get PyClips</a>
          </SurfaceFrame>
        </div>
      )}

      <main>
        <section className="landing-hero">
          <p className="landing-eyebrow">Windows desktop clip studio</p>
          <h1>
            Turn long videos into
            <br />
            <span>captioned vertical clips.</span>
          </h1>
          <p className="landing-lead">
            Import a video, find strong moments, reframe for 9:16,
            and burn styled captions ready to post.
          </p>
          <div className="landing-hero-ctas">
            <ExternalCta url={exeUrl} className="landing-btn landing-btn-primary landing-btn-lg">
              Download PyClips
            </ExternalCta>
            <ExternalCta url={MICROSOFT_STORE_URL} className="landing-btn landing-btn-store landing-btn-lg">
              Get it from Microsoft Store
            </ExternalCta>
          </div>
          <ul className="landing-trust" aria-label="Product highlights">
            <li>Windows app</li>
            <li>Styled captions</li>
            <li>GPU optional</li>
            <li>10 free clips</li>
          </ul>
          <p className="landing-meta"></p>
          <div className="landing-hero-visual">
            <Shot
              src="/screenshots/dashboard.webp"
              alt="PyClips dashboard with 9:16 preview, caption settings, and GPU processing"
              eager
            />
          </div>
        </section>

        <section className="landing-strip reveal" aria-label="Highlights">
          <h2>Built for creators who edit on Windows — not in the browser.</h2>
          <ul className="landing-pills">
            <li></li>
            <li>Caption style library</li>
            <li>Manual reframe keyframes</li>
            <li></li>
            <li>Music ducking</li>
          </ul>
        </section>

        <section className="landing-block reveal" id="product">
          <h2>From raw video to ready-to-post short.</h2>
          <p className="landing-subhead">PyClips handles the repetitive editing work so you can focus on the content.</p>
          <div className="landing-stages">
            <article>
              <span>01</span>
              <h3>Import</h3>
              <p>Drop in a video or paste a supported link.</p>
              <Shot src="/screenshots/create.webp" alt="PyClips create screen with upload and paste-link bar" />
            </article>
            <article>
              <span>02</span>
              <h3>Style</h3>
              <p>Choose captions, framing, effects and music.</p>
              <Shot src="/screenshots/captions.webp" alt="PyClips caption style picker beside a phone preview" />
            </article>
            <article>
              <span>03</span>
              <h3>Export</h3>
              <p>Render a polished short ready to post.</p>
              <Shot src="/screenshots/library.webp" alt="PyClips library with a finished vertical clip" />
            </article>
          </div>
        </section>

        <section className="landing-split reveal" id="features">
          <div>
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
          <Shot src="/screenshots/captions.webp" alt="Caption themes such as Hormozi and word highlighting on the preview" />
        </section>

        <section className="landing-split landing-split-rev reveal">
          <div>
            <h2>Turn landscape footage into vertical content.</h2>
            <p>
              Reframe your footage for 9:16, 16:9 or 1:1 without manually rebuilding every shot.
            </p>
            <ul className="landing-ratios">
              <li>9:16 Vertical</li>
              <li>16:9 Landscape</li>
              <li>1:1 Square</li>
            </ul>
            <p className="landing-note">Manual reframing and keyframes when you want precise control.</p>
          </div>
          <Shot src="/screenshots/dashboard.webp" alt="Aspect ratio controls set to 9:16 with a vertical phone preview" />
        </section>

        <section className="landing-split reveal">
          <div>
            <h2>Give every clip more energy.</h2>
            <p>
              Add background music, control volume, duck music under speech, and line tracks up with the beat.
            </p>
            <ul className="landing-feature-list">
              <li>Music waveform</li>
              <li>Volume</li>
              <li>Ducking</li>
              <li>Beat analysis</li>
            </ul>
          </div>
          <Shot src="/screenshots/add.webp" alt="PyClips editor with clip preview and workflow steps" />
        </section>

        <section className="landing-block reveal">
          <h2>One workflow. No editing headache.</h2>
          <ol className="landing-flow">
            <li>Import</li>
            <li>Transcribe</li>
            <li>Find moments</li>
            <li>Caption</li>
            <li>Reframe</li>
            <li>Add music</li>
            <li>Render</li>
            <li>Export</li>
          </ol>
        </section>

        <section className="landing-block reveal" id="pricing">
          <h2>Start creating with PyClips.</h2>
          <div className="landing-plans">
            <article className="landing-plan">
              <p className="landing-plan-name">Free</p>
              <p className="landing-plan-price">{pricing?.currency === "USD" ? "$0" : "₹0"}</p>
              <p className="landing-plan-meta">10 lifetime generated clips</p>
              <ul>
                <li>Caption generation</li>
                <li>Basic editing</li>
                <li>GPU acceleration</li>
              </ul>
              <ExternalCta url={exeUrl} className="landing-btn landing-btn-ghost landing-btn-full">
                Download PyClips
              </ExternalCta>
            </article>
            <article className="landing-plan landing-plan-hi">
              <p className="landing-plan-name">Premium</p>
              <p className="landing-plan-price">{pricing?.monthly_display || "₹19"} <small>/ month</small></p>
              <p className="landing-plan-meta">or {pricing?.yearly_display || "₹199"} / year</p>
              <ul>
                <li>Unlimited generations</li>
                <li>All caption styles</li>
                <li>Advanced features</li>
                <li>Premium features</li>
              </ul>
              <SurfaceFrame variant="primary" full>
                <a className="landing-btn landing-btn-primary landing-btn-full" href="/pay">Get Premium</a>
              </SurfaceFrame>
              <p className="landing-note">Billed on this website via Razorpay. Cancel autopay from Razorpay or your bank mandate.</p>
            </article>
          </div>
        </section>

        <section className="landing-block reveal" id="download">
          <h2>Get PyClips on Windows.</h2>
          <div className="landing-dl">
            <article>
              <h3>Direct download</h3>
              <p>{exeUrl ? "Windows installer (.exe). Click to start the download." : "The Windows installer will be available here when it is released."}</p>
              <ExternalCta url={exeUrl} className="landing-btn landing-btn-primary">
                Download PyClips
              </ExternalCta>
            </article>
            <article>
              <h3>Microsoft Store</h3>
              <p>Install PyClips from the Microsoft Store on Windows 10 and Windows 11.</p>
              <ExternalCta url={MICROSOFT_STORE_URL} className="landing-btn landing-btn-store">
                Microsoft Store
              </ExternalCta>
            </article>
          </div>
          <p className="landing-meta">Windows 10 / Windows 11</p>
        </section>

        <section className="landing-block reveal" id="faq">
          <h2>Questions</h2>
          <div className="landing-faq">
            {FAQS.map((item) => (
              <details key={item.q} className="landing-faq-item">
                <summary>{item.q}</summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </section>

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
      </main>

      <footer className="landing-foot">
        <div className="landing-foot-brand">
          <span className="landing-mark sm"><Bolt size={16} /></span>
          <div>
            <strong>PyClips</strong>
            <p>AI-powered video clipping for Windows.</p>
          </div>
        </div>
        <nav aria-label="Footer">
          <a href="#product">Product</a>
          <a href="#features">Features</a>
          <a href="#pricing">Pricing</a>
          <a href="#download">Download</a>
          <a href="/privacy">Privacy</a>
          <a href="/login">Login</a>
        </nav>
        <div className="landing-social">
          {SOCIALS.map((s) => (
            <a key={s.label} href={s.href} target="_blank" rel="noreferrer">{s.label}</a>
          ))}
        </div>
        <p className="landing-copy">© 2026 PyClips. All rights reserved.</p>
      </footer>
    </div>
  );
}
