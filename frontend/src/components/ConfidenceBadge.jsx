// Confidence answers "how sure are we?" -- deliberately separate from severity.

const LABELS = {
  high: {
    text: 'Verified',
    title: 'Checked by arithmetic against the playbook threshold. No model judgment involved.',
  },
  medium: {
    text: 'Confident',
    title: 'The model found unambiguous wording in the clause and quoted it.',
  },
  low: {
    text: 'Needs review',
    title: 'The model was not confident enough to act on this. A human should decide.',
  },
}

export default function ConfidenceBadge({ tier, source }) {
  if (!tier) return null

  const label = LABELS[tier] ?? { text: tier, title: '' }
  const suffix = source === 'deterministic' ? ' (arithmetic)' : ''

  return (
    <span className={`badge badge--tier-${tier}`} title={label.title}>
      {label.text}
      {suffix}
    </span>
  )
}
