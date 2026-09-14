import { useState } from 'react'

// Vendor language beside the proposed replacement, so the edit can be judged
// without hunting through the original document. Copy is here because the next
// thing a reviewer does is paste this into the contract.

export default function RedlineDiff({ original, proposed, changeSummary, addresses }) {
  const [copied, setCopied] = useState(false)

  if (!proposed) return null

  async function copy() {
    try {
      await navigator.clipboard.writeText(proposed)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      // Clipboard is blocked in some contexts; the text is on screen regardless.
    }
  }

  return (
    <div className="redline">
      {addresses?.length > 1 && (
        <p className="redline__combined">
          One replacement covering all {addresses.length} problems in this clause:{' '}
          {addresses.join(', ')}. Separate edits would undo each other.
        </p>
      )}

      <div className="redline__head">
        <span className="redline__summary">{changeSummary}</span>
        <button type="button" className="btn btn--ghost btn--sm" onClick={copy}>
          {copied ? 'Copied' : 'Copy replacement'}
        </button>
      </div>

      <div className="redline__cols">
        <div>
          <span className="redline__label redline__label--old">As proposed by vendor</span>
          <p className="redline__text redline__text--old">{original}</p>
        </div>
        <div>
          <span className="redline__label redline__label--new">Suggested replacement</span>
          <p className="redline__text redline__text--new">{proposed}</p>
        </div>
      </div>
    </div>
  )
}
