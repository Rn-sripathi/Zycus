// Answers "what do I actually need to look at?" before any scrolling.

export default function SummaryBar({ summary, filter, onFilter }) {
  if (!summary) return null

  const stats = [
    { key: 'all', label: 'Clauses reviewed', value: summary.clauses_reviewed },
    { key: 'deviation', label: 'Deviations', value: summary.deviations },
    { key: 'escalate', label: 'Escalate', value: summary.serious, tone: 'escalate' },
    { key: 'negotiable', label: 'Negotiable', value: summary.minor, tone: 'negotiable' },
    { key: 'review', label: 'Needs a human', value: summary.needs_review, tone: 'review' },
    { key: 'uncovered', label: 'No rule applies', value: summary.clauses_without_applicable_rule },
  ]

  const filters = [
    { key: 'all', label: 'Everything' },
    { key: 'review', label: 'Needs a human' },
    { key: 'escalate', label: 'Escalate only' },
    { key: 'deviation', label: 'All deviations' },
  ]

  return (
    <section className="card">
      <div className="card__body">
        <div className="stats">
          {stats.map((stat) => (
            <div key={stat.label} className={`stat ${stat.tone ? `stat--${stat.tone}` : ''}`}>
              <span className="stat__value">{stat.value}</span>
              <span className="stat__label">{stat.label}</span>
            </div>
          ))}
        </div>

        <div className="summary__foot">
          <div className="filters">
            {filters.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`chip ${filter === item.key ? 'chip--on' : ''}`}
                onClick={() => onFilter(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <span className="summary__timing">
            Completed in {Number(summary.elapsed_seconds).toFixed(2)}s
          </span>
        </div>
      </div>
    </section>
  )
}
