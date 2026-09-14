import { useRef, useState } from 'react'
import { exportPlaybook, validatePlaybook } from '../api/client.js'

// Rules are loaded as structured JSON rather than typed as sentences. A rule
// written as prose can only ever be judged by the model; one carrying a
// threshold, a unit and anchor phrases can still be settled by arithmetic, which
// is what keeps findings on the verified tier.

export default function PlaybookLoader({ custom, onApply, onReset }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [summary, setSummary] = useState(null)
  const [isChecking, setIsChecking] = useState(false)
  const fileRef = useRef(null)

  async function loadStarter() {
    try {
      const rules = await exportPlaybook()
      setText(JSON.stringify(rules, null, 2))
      setError('')
      setSummary(null)
    } catch (err) {
      setError(err.message)
    }
  }

  async function readFile(file) {
    if (!file) return
    try {
      const contents = await file.text()
      setText(contents)
      setError('')
      setSummary(null)
    } catch {
      setError('That file could not be read as text.')
    }
  }

  async function apply() {
    setIsChecking(true)
    setError('')
    setSummary(null)

    let parsed
    try {
      parsed = JSON.parse(text)
    } catch (err) {
      setError(`That is not valid JSON. ${err.message}`)
      setIsChecking(false)
      return
    }

    try {
      const result = await validatePlaybook(parsed)
      if (!result.valid) {
        setError(result.error)
        return
      }
      setSummary(result)
      onApply(Array.isArray(parsed) ? parsed : parsed.rules ?? parsed.playbook)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsChecking(false)
    }
  }

  return (
    <section className="side-section">
      <div className="side-section__head">
        <span className="side-section__title">Custom playbook</span>
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? 'Close' : custom ? 'Change' : 'Load'}
        </button>
      </div>

      {custom && !open && (
        <div className="pb-active">
          <span>
            Using a custom playbook of <b>{custom.length}</b> rules.
          </span>
          <button type="button" className="btn btn--ghost btn--sm" onClick={onReset}>
            Back to the Zycus playbook
          </button>
        </div>
      )}

      {open && (
        <div className="pb-editor">
          <p className="pb-help">
            Rules are structured, not prose. Numeric rules need a threshold, a unit and
            anchor phrases, which is what lets them be checked by arithmetic rather than
            judged by the model.
          </p>

          <div className="pb-actions">
            <button type="button" className="btn btn--ghost btn--sm" onClick={loadStarter}>
              Start from current
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => fileRef.current?.click()}
            >
              Open .json
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".json,application/json"
              hidden
              onChange={(event) => {
                readFile(event.target.files?.[0])
                event.target.value = ''
              }}
            />
          </div>

          <textarea
            className="editor pb-json"
            value={text}
            spellCheck={false}
            onChange={(event) => setText(event.target.value)}
            placeholder='[{ "id": "warranty_period", "title": "Warranty period", … }]'
          />

          {error && <p className="pb-error">{error}</p>}

          {summary && (
            <p className="pb-ok">
              Applied {summary.rule_count} rules — {summary.numeric_rules} checked by
              arithmetic, {summary.qualitative_rules} by reading.
            </p>
          )}

          <button
            type="button"
            className="btn btn--primary btn--sm btn--block"
            onClick={apply}
            disabled={isChecking || !text.trim()}
          >
            {isChecking ? 'Checking…' : 'Validate and apply'}
          </button>
        </div>
      )}
    </section>
  )
}
