// Severity answers "how bad is it?" -- independent of how sure we are.

const LABELS = {
  serious: {
    text: 'Escalate',
    title: 'Serious deviation. Escalate to legal or commercial owner before signing.',
  },
  minor: {
    text: 'Negotiable',
    title: 'Minor deviation. Reasonable to negotiate rather than escalate.',
  },
}

export default function SeverityBadge({ severity }) {
  if (!severity) return null

  const label = LABELS[severity] ?? { text: severity, title: '' }

  return (
    <span className={`badge badge--severity-${severity}`} title={label.title}>
      {label.text}
    </span>
  )
}
