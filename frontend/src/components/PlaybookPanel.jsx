// The rulebook the contract is judged against. Visible so a reviewer can see what
// the agent was and was not looking for.

export default function PlaybookPanel({ rules }) {
  if (!rules?.length) return null

  return (
    <details className="panel playbook">
      <summary className="playbook__summary">
        Playbook in use — {rules.length} rules
      </summary>
      <ul className="playbook__list">
        {rules.map((rule) => (
          <li key={rule.id} className="playbook__rule">
            <div className="playbook__rule-head">
              <strong>{rule.title}</strong>
              <span className={`badge badge--severity-${rule.default_severity}`}>
                {rule.default_severity === 'serious' ? 'Escalate' : 'Negotiable'}
              </span>
              <span className="badge badge--type">
                {rule.rule_type === 'numeric' ? 'Checked by arithmetic' : 'Checked by reading'}
              </span>
            </div>
            <p className="playbook__rule-text">{rule.text}</p>
            <p className="playbook__rule-why">{rule.rationale}</p>
          </li>
        ))}
      </ul>
    </details>
  )
}
