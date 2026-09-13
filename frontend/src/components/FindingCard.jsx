import ConfidenceBadge from './ConfidenceBadge.jsx'
import SeverityBadge from './SeverityBadge.jsx'
import RedlineDiff from './RedlineDiff.jsx'

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
    original_text,
    review_reasons,
    numeric,
  } = finding

  return (
    <article className={`finding finding--${verdict} ${needs_review ? 'finding--review' : ''}`}>
      <header className="finding__header">
        <div>
          <h3 className="finding__title">
            Clause {clause_number}
            {clause_heading ? ` — ${clause_heading}` : ''}
          </h3>
          {rule_title ? (
            <p className="finding__rule">Checked against: {rule_title}</p>
          ) : (
            <p className="finding__rule">No playbook rule covers this clause</p>
          )}
        </div>
        <div className="finding__badges">
          <SeverityBadge severity={severity} />
          <ConfidenceBadge tier={tier} source={source} />
        </div>
      </header>

      {explanation && <p className="finding__explanation">{explanation}</p>}

      {numeric?.found_value != null && (
        <p className="finding__arithmetic">
          Read <strong>{numeric.found_value} {numeric.unit}</strong> from the clause; playbook
          requires <strong>{numeric.threshold} {numeric.unit}</strong>.
        </p>
      )}

      {evidence_quote && (
        <blockquote className="finding__evidence">“{evidence_quote}”</blockquote>
      )}

      {needs_review && review_reasons?.length > 0 && (
        <div className="finding__review-reasons">
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
      />
    </article>
  )
}
