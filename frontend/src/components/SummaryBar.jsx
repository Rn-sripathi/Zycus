// Answers "what do I actually need to look at?" before any scrolling.

export default function SummaryBar({ summary }) {
  if (!summary) return null

  const stats = [
    { label: 'Clauses reviewed', value: summary.clauses_reviewed },
    { label: 'Deviations found', value: summary.deviations },
    { label: 'Escalate', value: summary.serious, tone: 'serious' },
    { label: 'Negotiable', value: summary.minor, tone: 'minor' },
    { label: 'Needs human review', value: summary.needs_review, tone: 'review' },
    { label: 'Not covered by playbook', value: summary.clauses_without_applicable_rule },
  ]

  return (
    <section className="summary">
      <div className="summary__stats">
        {stats.map((stat) => (
          <div key={stat.label} className={`stat ${stat.tone ? `stat--${stat.tone}` : ''}`}>
            <span className="stat__value">{stat.value}</span>
            <span className="stat__label">{stat.label}</span>
          </div>
        ))}
      </div>
      <p className="summary__timing">
        Completed in {Number(summary.elapsed_seconds).toFixed(2)}s
      </p>
    </section>
  )
}
