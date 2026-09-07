import BrandLogo from "../BrandLogo.jsx";

const FRAMES = [
  { time: "00:12", tone: "a", tag: "Hook", sub: "Clip in" },
  { time: "00:34", tone: "b", tag: "Word-by-word", sub: "Captions on" },
  { time: "01:02", tone: "c", tag: "Local MP4", sub: "Export" },
];

function Waveform() {
  return (
    <svg className="auth-stitch__wave-svg" viewBox="0 0 400 32" fill="none" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 16 Q 10 4, 20 16 T 40 16 T 60 8 T 80 24 T 100 6 T 120 26 T 140 12 T 160 20 T 180 2 T 200 30 T 220 14 T 240 18 T 260 8 T 280 24 T 300 10 T 320 22 T 340 16 T 360 26 T 380 12 T 400 16" stroke="currentColor" strokeLinecap="round" strokeWidth="1.75" />
      <path d="M120 16 Q 130 8, 140 16 T 160 16 T 180 4 T 200 28 T 220 12" stroke="#ffb020" strokeLinecap="round" strokeWidth="2.25" />
    </svg>
  );
}

function Eq({ gold = false }) {
  return (
    <div className={"auth-stitch__eq" + (gold ? " auth-stitch__eq--gold" : "")} aria-hidden="true">
      <span /><span /><span /><span /><span />
    </div>
  );
}

export default function AuthStitchShowcase({ variant = "web" }) {
  const isWeb = variant === "web";

  return (
    <aside className="auth-stitch">
      <div className="auth-stitch__identity">
        <div className="auth-stitch__badge">
          <span className="auth-stitch__mark"><BrandLogo size={28} /></span>
          <span>PyClips</span>
        </div>
        <div className="auth-stitch__livechip">
          <span className="auth-stitch__live" />
          Auto caption & clip studio
        </div>
      </div>

      <div className="auth-stitch__copy">
        <h2 className="auth-stitch__title">
          {isWeb ? <>Account for your <em>clip studio</em></> : <>Stitch moments into <em>shorts</em></>}
        </h2>
        <p className="auth-stitch__lead">
          {isWeb
            ? "Premium, coupons, and billing live here. Your videos still render locally in the Windows app."
            : "Transcribe on your PC, pick clip windows, burn captions, and export MP4s — nothing uploads to the cloud."}
        </p>
      </div>

      <div className="auth-stitch__stage">
        <div className="auth-stitch__nle">
          <div className="auth-stitch__nle-bar">
            <span className="auth-stitch__dots" aria-hidden="true"><i /><i /><i /></span>
            <span className="auth-stitch__filename">SHORT_09x16.PYC</span>
            <span className="auth-stitch__tc">00:00:34:12</span>
          </div>
          <div className="auth-stitch__rail" />
          <div className="auth-stitch__frames">
            {FRAMES.map((clip) => (
              <div key={clip.time} className={`auth-stitch__frame auth-stitch__frame--${clip.tone}`}>
                <div className="auth-stitch__frame-top">
                  <span className="auth-stitch__frame-time">{clip.time}</span>
                  <span className="auth-stitch__frame-cap">Aa</span>
                </div>
                <div className="auth-stitch__frame-bot">
                  <Eq gold={clip.tone === "b"} />
                  <div className="auth-stitch__frame-tag">
                    <strong>{clip.tag}</strong>
                    <span>{clip.sub}</span>
                  </div>
                </div>
              </div>
            ))}
            <span className="auth-stitch__needle" aria-hidden="true" />
          </div>
          <div className="auth-stitch__wave">
            <Waveform />
            <div className="auth-stitch__marks">
              <span>00:00</span>
              <span>00:15</span>
              <span className="on">00:30</span>
              <span>00:45</span>
              <span>01:00</span>
            </div>
          </div>
        </div>
      </div>

      <ul className="auth-stitch__facts">
        <li>9:16 · 16:9 · 1:1 export</li>
        <li>{isWeb ? "Sync Premium to desktop" : "10 free clips included"}</li>
        <li>Word-by-word captions</li>
      </ul>
    </aside>
  );
}
