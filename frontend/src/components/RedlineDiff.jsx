// Shows the vendor's language beside the proposed replacement, so a reviewer can
// judge the edit without hunting through the original document.

export default function RedlineDiff({ original, proposed, changeSummary, addresses }) {
  if (!proposed) return null

  return (
    <div className="redline">
      {addresses?.length > 1 && (
        <p className="redline__combined">
          One replacement, fixing all {addresses.length} issues in this clause:{' '}
          {addresses.join(', ')}. Applying a separate edit per issue would undo the others.
        </p>
      )}
      {changeSummary && <p className="redline__summary">{changeSummary}</p>}
      <div className="redline__columns">
        <div className="redline__column">
          <h5 className="redline__label redline__label--original">As proposed by Vendor</h5>
          <p className="redline__text redline__text--original">{original}</p>
        </div>
        <div className="redline__column">
          <h5 className="redline__label redline__label--proposed">Suggested replacement</h5>
          <p className="redline__text redline__text--proposed">{proposed}</p>
        </div>
      </div>
    </div>
  )
}
