// Playbook and history live together in the rail: both answer "what is this
// judged against, and what has it judged before?" without taking room from the
// contract itself.

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

import PlaybookLoader from './PlaybookLoader.jsx'

export default function Sidebar({
  open,
  rules,
  customPlaybook,
  onApplyPlaybook,
  onResetPlaybook,
  reviews,
  activeId,
  onOpenReview,
  onDeleteReview,
  isBusy,
  showHistory,
}) {
  return (
    <aside className={`sidebar ${open ? 'sidebar--open' : ''}`}>
      <section className="side-section">
        <div className="side-section__head">
          <span className="side-section__title">
            {customPlaybook ? "Playbook (custom)" : "Playbook"}
          </span>
          <span className="count">{rules.length}</span>
        </div>

        <div className="rules">
          {rules.map((rule) => (
            <article key={rule.id} className="rule">
              <div className="rule__top">
                <span className="rule__name">{rule.title}</span>
                <span
                  className={`rule__how ${rule.rule_type === 'numeric' ? 'rule__how--math' : ''}`}
                >
                  {rule.rule_type === 'numeric' ? 'maths' : 'reading'}
                </span>
              </div>
              <p className="rule__text">{rule.text}</p>
            </article>
          ))}
        </div>
      </section>

      <PlaybookLoader
        custom={customPlaybook}
        onApply={onApplyPlaybook}
        onReset={onResetPlaybook}
      />

      {showHistory && (
        <section className="side-section">
          <div className="side-section__head">
            <span className="side-section__title">Past reviews</span>
            {reviews.length > 0 && <span className="count">{reviews.length}</span>}
          </div>

          {reviews.length === 0 ? (
            <p className="history__empty">
              Reviews you run are saved here with their findings.
            </p>
          ) : (
            <div className="history">
              {reviews.map((item) => (
                <div
                  key={item.id}
                  className={`history__row ${item.id === activeId ? 'history__row--active' : ''}`}
                >
                  <button
                    type="button"
                    className="history__open"
                    onClick={() => onOpenReview(item.id)}
                    disabled={isBusy}
                  >
                    <span className="history__name">{item.label || 'Untitled contract'}</span>
                    <span className="history__meta">
                      {timeAgo(item.created_at)} · {item.summary.deviations} deviations
                      {item.summary.needs_review > 0 && (
                        <> · <b>{item.summary.needs_review} flagged</b></>
                      )}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="history__del"
                    onClick={() => onDeleteReview(item.id)}
                    aria-label={`Delete review ${item.label || 'untitled'}`}
                    title="Delete"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </aside>
  )
}
