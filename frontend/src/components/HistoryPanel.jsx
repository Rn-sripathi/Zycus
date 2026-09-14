// Past reviews. A contract review tool needs an audit trail: what was concluded
// about which draft, when, and what was left for a human.

function when(iso) {
  const date = new Date(iso)
  const mins = Math.round((Date.now() - date.getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  if (mins < 1440) return `${Math.round(mins / 60)}h ago`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function HistoryPanel({
  reviews,
  activeId,
  onOpen,
  onDelete,
  isLoading,
}) {
  if (!reviews) return null

  return (
    <details className="panel history" open={reviews.length > 0}>
      <summary className="history__summary">
        Past reviews
        {reviews.length > 0 && <span className="group__count">{reviews.length}</span>}
      </summary>

      {reviews.length === 0 ? (
        <p className="history__empty">
          Nothing saved yet. Each review you run is stored here with its findings.
        </p>
      ) : (
        <ul className="history__list">
          {reviews.map((item) => (
            <li
              key={item.id}
              className={`history__item ${item.id === activeId ? 'history__item--active' : ''}`}
            >
              <button
                type="button"
                className="history__open"
                onClick={() => onOpen(item.id)}
                disabled={isLoading}
              >
                <span className="history__label">
                  {item.label || 'Untitled contract'}
                </span>
                <span className="history__meta">
                  {when(item.created_at)} · {item.summary.clauses_reviewed} clauses ·{' '}
                  {item.summary.deviations} deviations
                  {item.summary.needs_review > 0 && (
                    <span className="history__flagged">
                      {' '}
                      · {item.summary.needs_review} flagged
                    </span>
                  )}
                </span>
              </button>
              <button
                type="button"
                className="history__delete"
                onClick={() => onDelete(item.id)}
                title="Delete this review"
                aria-label={`Delete review of ${item.label || 'untitled contract'}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </details>
  )
}
