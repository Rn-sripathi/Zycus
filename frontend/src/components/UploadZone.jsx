import { useRef, useState } from 'react'

// Uploading never runs a review. The extracted text lands in the editor first,
// so the reviewer sees what was actually read out of their file, and can fix it,
// before a model call is spent on it. PDFs in particular do not always survive
// extraction cleanly.

const ACCEPT = '.txt,.md,.text,.pdf,.docx'

export default function UploadZone({ onFile, isBusy, lastFile }) {
  const inputRef = useRef(null)
  const [isOver, setIsOver] = useState(false)

  function choose(fileList) {
    const file = fileList?.[0]
    if (file) onFile(file)
  }

  return (
    <>
      <div
        className={`upload ${isOver ? 'upload--over' : ''} ${isBusy ? 'upload--busy' : ''}`}
        onClick={() => !isBusy && inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            if (!isBusy) inputRef.current?.click()
          }
        }}
        onDragOver={(event) => {
          event.preventDefault()
          setIsOver(true)
        }}
        onDragLeave={() => setIsOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsOver(false)
          if (!isBusy) choose(event.dataTransfer.files)
        }}
        role="button"
        tabIndex={0}
        aria-label="Upload a contract file"
      >
        <svg
          className="upload__icon"
          width="22"
          height="22"
          viewBox="0 0 22 22"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M11 15V4m0 0L6.5 8.5M11 4l4.5 4.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M3 14v2.5A2.5 2.5 0 0 0 5.5 19h11a2.5 2.5 0 0 0 2.5-2.5V14"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>

        <span className="upload__title">
          {isBusy ? 'Reading your file…' : 'Drop a contract here, or click to browse'}
        </span>
        <span className="upload__sub">PDF, Word or plain text, up to 10 MB</span>

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          hidden
          onChange={(event) => {
            choose(event.target.files)
            event.target.value = '' // allow re-uploading the same file
          }}
        />
      </div>

      {lastFile && (
        <div className="upload__file">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path
              d="M2 7.5 5.5 11 12 3.5"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>
            Read <b>{lastFile.filename}</b> — {lastFile.clauses_detected} clauses found in{' '}
            {lastFile.characters.toLocaleString()} characters
          </span>
        </div>
      )}
    </>
  )
}
