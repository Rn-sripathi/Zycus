// How bad is it? Independent of how sure we are.

const LABELS = {
  serious: {
    text: 'Escalate',
    title: 'Serious deviation. Escalate before signing.',
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
    <span className={`badge badge--${severity}`} title={label.title}>
      {label.text}
    </span>
  )
}
