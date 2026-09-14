// How sure are we? Deliberately separate from how bad it is.

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
    title: 'Not confident enough to act on. A human should decide.',
  },
}

export default function ConfidenceBadge({ tier, source }) {
  if (!tier) return null
  const label = LABELS[tier] ?? { text: tier, title: '' }

  return (
    <span className={`badge badge--${tier}`} title={label.title}>
      {label.text}
      {source === 'deterministic' && ' · maths'}
    </span>
  )
}
