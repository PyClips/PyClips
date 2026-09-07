export default function AuthGateShell({ showcase, panel, footer = null }) {
  return (
    <div className="auth-gate">
      <div className="auth-gate__fx" aria-hidden="true">
        <span className="auth-gate__orb auth-gate__orb--a" />
        <span className="auth-gate__orb auth-gate__orb--b" />
        <span className="auth-gate__grid" />
      </div>
      <div className="auth-gate__canvas">
        {showcase}
        <div className="auth-gate__panel-wrap">
          <div className="auth-gate__panel">{panel}</div>
        </div>
      </div>
      {footer}
    </div>
  );
}
