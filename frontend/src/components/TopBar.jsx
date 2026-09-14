// Status belongs where it is always visible: whether the model and the database
// are actually reachable decides whether anything on this page will work.

function Dot({ on }) {
  return <span className={`pill__dot ${on ? '' : 'pill__dot--off'}`} />
}

export default function TopBar({ health, theme, onToggleTheme, onToggleSidebar }) {
  return (
    <header className="topbar">
      <button
        type="button"
        className="icon-button sidebar-toggle"
        onClick={onToggleSidebar}
        aria-label="Toggle playbook and history"
      >
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
          <path d="M1.5 3.5h12M1.5 7.5h12M1.5 11.5h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </button>

      <div className="brand">
        <span className="brand__mark">Z</span>
        <div>
          <div className="brand__name">Redlining Agent</div>
          <div className="brand__sub">Contract review against the Zycus playbook</div>
        </div>
      </div>

      <div className="topbar__spacer" />

      <div className="topbar__status">
        {health && (
          <>
            <span className={`pill ${health.llm_configured ? '' : 'pill--warn'}`}>
              <Dot on={health.llm_configured} />
              {health.llm_configured ? health.model : 'No API key'}
            </span>
            <span className="pill">
              <Dot on={health.persistence_enabled} />
              {health.persistence_enabled ? 'Saving reviews' : 'Not saving'}
            </span>
          </>
        )}

        <button
          type="button"
          className="icon-button"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
        >
          {theme === 'dark' ? (
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
              <circle cx="7.5" cy="7.5" r="3" stroke="currentColor" strokeWidth="1.3" />
              <path
                d="M7.5 1v1.5M7.5 12.5V14M14 7.5h-1.5M2.5 7.5H1M12.1 2.9l-1 1M3.9 11.1l-1 1M12.1 12.1l-1-1M3.9 3.9l-1-1"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinecap="round"
              />
            </svg>
          ) : (
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden="true">
              <path
                d="M13 9.3A5.8 5.8 0 0 1 5.7 2a5.9 5.9 0 1 0 7.3 7.3Z"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </button>
      </div>
    </header>
  )
}
