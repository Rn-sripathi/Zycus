import { useEffect, useMemo, useState } from 'react'
import {
  deleteReview,
  getHealth,
  getPlaybook,
  getReview,
  getSamples,
  listReviews,
  reviewContract,
  uploadContract,
} from './api/client.js'
import ContractInput from './components/ContractInput.jsx'
import FindingCard from './components/FindingCard.jsx'
import Sidebar from './components/Sidebar.jsx'
import SummaryBar from './components/SummaryBar.jsx'
import TopBar from './components/TopBar.jsx'

// Findings are grouped by what the reviewer should do with them, not by clause
// order: anything the agent declined to act on comes first.
const GROUPS = [
  {
    id: 'review',
    title: 'Flagged for human review',
    blurb: 'The agent was not confident enough to act on these on its own.',
    match: (f) => f.needs_review,
  },
  {
    id: 'deviation',
    title: 'Deviations with suggested redlines',
    blurb: 'Confident enough to propose replacement language.',
    match: (f) => f.verdict === 'deviation' && !f.needs_review,
  },
  {
    id: 'compliant',
    title: 'Checked and compliant',
    blurb: 'Assessed against a playbook rule and passed.',
    match: (f) => f.verdict === 'compliant' && !f.needs_review,
  },
  {
    id: 'uncovered',
    title: 'Not covered by the playbook',
    blurb: 'No rule governs these clauses, so they were not assessed.',
    match: (f) => f.verdict === 'no_applicable_rule',
  },
]

const FILTERS = {
  all: () => true,
  review: (f) => f.needs_review,
  escalate: (f) => f.severity === 'serious',
  deviation: (f) => f.verdict === 'deviation',
}

const PIPELINE_STEPS = [
  'segmenting clauses',
  'matching rules',
  'checking thresholds',
  'reading wording',
  'drafting redlines',
  'routing for review',
]

const CLAUSE_START = /^[ \t]*\d{1,2}[.)]\s+/gm

export default function App() {
  const [contractText, setContractText] = useState('')
  const [samples, setSamples] = useState(null)
  const [rules, setRules] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [isReviewing, setIsReviewing] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [health, setHealth] = useState(null)
  const [history, setHistory] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [label, setLabel] = useState('Northwind vendor services agreement')
  const [lastFile, setLastFile] = useState(null)
  const [filter, setFilter] = useState('all')
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || 'light',
  )
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    getSamples()
      .then((data) => {
        setSamples(data)
        setContractText(data.sample_contract)
      })
      .catch((err) => setError(err.message))

    getPlaybook().then(setRules).catch(() => {})
    getHealth().then(setHealth).catch(() => {})
    refreshHistory()
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('zra-theme', theme)
    } catch {
      // Private mode blocks storage; the toggle still works for this session.
    }
  }, [theme])

  // Rough client-side count, shown only to reassure before a review runs.
  // The server does the real segmentation.
  const clauseCount = useMemo(
    () => (contractText.match(CLAUSE_START) || []).length,
    [contractText],
  )

  function refreshHistory() {
    listReviews()
      .then(setHistory)
      .catch(() => setHistory([]))
  }

  function show(data, id) {
    setResult(data)
    setActiveId(id)
    setFilter('all')
  }

  async function handleReview() {
    setIsReviewing(true)
    setError('')
    setResult(null)

    try {
      const data = await reviewContract(contractText, label)
      show(data, data.review_id ?? null)
      if (data.review_id) refreshHistory()
    } catch (err) {
      setError(err.message)
    } finally {
      setIsReviewing(false)
    }
  }

  async function handleFile(file) {
    setIsUploading(true)
    setError('')

    try {
      const data = await uploadContract(file)
      setContractText(data.contract_text)
      setLastFile(data)
      setLabel(data.filename.replace(/\.[^.]+$/, ''))
      if (data.warning) setError(data.warning)
    } catch (err) {
      setError(err.message)
      setLastFile(null)
    } finally {
      setIsUploading(false)
    }
  }

  async function handleOpenReview(id) {
    setIsReviewing(true)
    setError('')
    setSidebarOpen(false)

    try {
      const data = await getReview(id)
      show(data, id)
      if (data.contract_text) setContractText(data.contract_text)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsReviewing(false)
    }
  }

  async function handleDeleteReview(id) {
    try {
      await deleteReview(id)
      if (id === activeId) {
        setActiveId(null)
        setResult(null)
      }
      refreshHistory()
    } catch (err) {
      setError(err.message)
    }
  }

  const findings = (result?.findings ?? []).filter(FILTERS[filter])

  return (
    <div className="app">
      <TopBar
        health={health}
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        onToggleSidebar={() => setSidebarOpen((open) => !open)}
      />

      <Sidebar
        open={sidebarOpen}
        rules={rules}
        reviews={history}
        activeId={activeId}
        onOpenReview={handleOpenReview}
        onDeleteReview={handleDeleteReview}
        isBusy={isReviewing}
        showHistory={Boolean(health?.persistence_enabled)}
      />

      <main className="main">
        <div className="main__inner">
          {health && !health.llm_configured && (
            <div className="alert alert--warn">
              No API key is configured on the server, so reviews cannot run. Set
              OPENAI_API_KEY and restart.
            </div>
          )}

          <ContractInput
            value={contractText}
            onChange={setContractText}
            onReview={handleReview}
            onLoadSample={() => samples && setContractText(samples.sample_contract)}
            onLoadAmbiguous={() => samples && setContractText(samples.ambiguous_contract)}
            onFile={handleFile}
            isReviewing={isReviewing}
            isUploading={isUploading}
            lastFile={lastFile}
            label={label}
            onLabelChange={setLabel}
            clauseCount={clauseCount}
          />

          {error && <div className="alert alert--error">{error}</div>}

          {isReviewing && (
            <section className="card">
              <div className="card__body progress">
                <div className="progress__track">
                  <div className="progress__bar" />
                </div>
                <div className="progress__steps">
                  {PIPELINE_STEPS.map((step) => (
                    <span key={step} className="progress__step">
                      {step}
                    </span>
                  ))}
                </div>
              </div>
            </section>
          )}

          {result && (
            <>
              <SummaryBar summary={result.summary} filter={filter} onFilter={setFilter} />

              {findings.length === 0 && (
                <div className="card">
                  <div className="empty">
                    <span className="empty__title">Nothing matches this filter</span>
                    <span className="empty__body">
                      Switch back to Everything to see the full review.
                    </span>
                  </div>
                </div>
              )}

              {GROUPS.map((group) => {
                const rows = findings.filter(group.match)
                if (!rows.length) return null

                return (
                  <section key={group.id} className="group">
                    <div className="group__head">
                      <h2>{group.title}</h2>
                      <span className="count">{rows.length}</span>
                      <p className="group__blurb">{group.blurb}</p>
                    </div>
                    {rows.map((finding) => (
                      <FindingCard
                        key={`${finding.clause_number}-${finding.rule_id ?? 'none'}`}
                        finding={finding}
                      />
                    ))}
                  </section>
                )
              })}
            </>
          )}

          {!result && !isReviewing && (
            <div className="card">
              <div className="empty">
                <span className="empty__title">No review yet</span>
                <span className="empty__body">
                  Upload a contract or load one of the samples, then press Review contract.
                  Deterministic checks run in Python before any model call, so threshold
                  findings are arithmetic rather than model judgment.
                </span>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
