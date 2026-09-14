import ConfidenceBadge from './ConfidenceBadge.jsx'
import RedlineDiff from './RedlineDiff.jsx'
import SeverityBadge from './SeverityBadge.jsx'

export default function FindingCard({ finding }) {
  const {
    clause_number,
    clause_heading,
    rule_title,
    verdict,
    tier,
    severity,
    source,
    needs_review,
    evidence_quote,
    explanation,
    proposed_redline,
    change_summary,
    redline_addresses,
    original_text,
    review_reasons,
    numeric,
  } = finding

  return (
    <article className={`finding finding--${verdict} ${needs_review ? 'finding--review' : ''}`}>
      <header className="finding__head">
        <div>
          <div className="finding__clause">Clause {clause_number}</div>
          <h3 className="finding__title">{clause_heading || 'Untitled clause'}</h3>
          <p className="finding__rule">
            {rule_title ? `Checked against: ${rule_title}` : 'No playbook rule covers this clause'}
          </p>
        </div>
        <div className="finding__badges">
          <SeverityBadge severity={severity} />
          <ConfidenceBadge tier={tier} source={source} />
        </div>
      </header>

      {explanation && <p className="finding__why">{explanation}</p>}

      {numeric?.found_value != null && (
        <p className="finding__math">
          read <b>{numeric.found_value} {numeric.unit}</b> · playbook requires{' '}
          <b>{numeric.threshold} {numeric.unit}</b>
        </p>
      )}

      {evidence_quote && <blockquote className="finding__quote">“{evidence_quote}”</blockquote>}

      {needs_review && review_reasons?.length > 0 && (
        <div className="finding__reasons">
          <h4>Why this needs a human</h4>
          <ul>
            {review_reasons.map((reason, index) => (
              <li key={index}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <RedlineDiff
        original={original_text}
        proposed={proposed_redline}
        changeSummary={change_summary}
        addresses={redline_addresses}
      />
    </article>
  )
}
