export default function ContractInput({
  value,
  onChange,
  onReview,
  onLoadSample,
  onLoadAmbiguous,
  isReviewing,
  label,
  onLabelChange,
}) {
  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Counterparty contract</h2>
        <div className="panel__actions">
          <button type="button" className="button button--ghost" onClick={onLoadSample}>
            Load sample contract
          </button>
          <button type="button" className="button button--ghost" onClick={onLoadAmbiguous}>
            Load ambiguous draft
          </button>
        </div>
      </div>

      {onLabelChange && (
        <label className="field">
          <span className="field__label">Name this review</span>
          <input
            className="field__input"
            type="text"
            value={label}
            onChange={(event) => onLabelChange(event.target.value)}
            placeholder="e.g. Northwind vendor services agreement"
          />
        </label>
      )}

      <textarea
        className="contract-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
        placeholder="Paste a contract with numbered clauses, e.g. “1. Term and Termination. ...”"
      />

      <div className="panel__footer">
        <button
          type="button"
          className="button button--primary"
          onClick={onReview}
          disabled={isReviewing || !value.trim()}
        >
          {isReviewing ? 'Reviewing…' : 'Review contract'}
        </button>
        <span className="hint">
          Runs six steps: segment, match rules, check thresholds, assess wording, draft
          redlines, then decide what needs a human.
        </span>
      </div>
    </section>
  )
}
