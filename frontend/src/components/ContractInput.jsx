import { useEffect, useRef, useState } from 'react'
import UploadZone from './UploadZone.jsx'

// Where the text in the editor came from. Without this the editor is just a box
// of text, and replacing it with a near-identical document looks like nothing
// happened -- which is exactly what uploading the sample contract as a PDF does.
const SOURCES = {
  sample: { label: 'Sample contract', tone: '' },
  ambiguous: { label: 'Ambiguous draft', tone: 'src--warn' },
  upload: { label: 'Uploaded file', tone: 'src--ok' },
  history: { label: 'Loaded from history', tone: '' },
  edited: { label: 'Edited by you', tone: '' },
}

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
  source,
}) {
  const [flash, setFlash] = useState(false)
  const firstRender = useRef(true)

  // Briefly outline the editor whenever the text is replaced from elsewhere, so
  // a swap between two similar documents is still felt.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    if (source === 'edited') return

    setFlash(true)
    const timer = setTimeout(() => setFlash(false), 900)
    return () => clearTimeout(timer)
  }, [source, value])

  const meta = SOURCES[source] ?? SOURCES.sample

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
          <div className="field__row">
            <label className="field__label" htmlFor="contract-text">
              Contract text
            </label>
            <span className={`src ${meta.tone}`}>{meta.label}</span>
          </div>
          <textarea
            id="contract-text"
            className={`editor ${flash ? "editor--flash" : ""}`}
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
