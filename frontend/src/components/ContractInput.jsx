import UploadZone from './UploadZone.jsx'

export default function ContractInput({
  value,
  onChange,
  onReview,
  onLoadSample,
  onLoadAmbiguous,
  onFile,
  isReviewing,
  isUploading,
  lastFile,
  label,
  onLabelChange,
  clauseCount,
}) {
  return (
    <section className="card">
      <div className="card__head">
        <div>
          <h2 className="card__title">Counterparty contract</h2>
          <p className="card__hint">Upload a file, or paste text with numbered clauses.</p>
        </div>
        <div className="card__actions">
          <button type="button" className="btn btn--ghost btn--sm" onClick={onLoadSample}>
            Sample contract
          </button>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onLoadAmbiguous}>
            Ambiguous draft
          </button>
        </div>
      </div>

      <div className="card__body">
        <UploadZone onFile={onFile} isBusy={isUploading} lastFile={lastFile} />

        <div className="field" style={{ marginTop: 16 }}>
          <label className="field__label" htmlFor="review-name">
            Name this review
          </label>
          <input
            id="review-name"
            className="input"
            type="text"
            value={label}
            onChange={(event) => onLabelChange(event.target.value)}
            placeholder="e.g. Northwind vendor services agreement"
          />
        </div>

        <div className="field">
          <label className="field__label" htmlFor="contract-text">
            Contract text
          </label>
          <textarea
            id="contract-text"
            className="editor"
            value={value}
            spellCheck={false}
            onChange={(event) => onChange(event.target.value)}
            placeholder={'1. Term and Termination. This Agreement shall commence…'}
          />
        </div>

        <div className="editor__foot">
          <button
            type="button"
            className="btn btn--primary"
            onClick={onReview}
            disabled={isReviewing || isUploading || !value.trim()}
          >
            {isReviewing ? 'Reviewing…' : 'Review contract'}
          </button>
          <span className="editor__stats">
            {value.length.toLocaleString()} characters · {clauseCount} numbered clauses
          </span>
        </div>
      </div>
    </section>
  )
}
