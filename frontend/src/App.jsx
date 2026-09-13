import { useEffect, useState } from 'react'
import { getHealth, getPlaybook, getSamples, reviewContract } from './api/client.js'
import ContractInput from './components/ContractInput.jsx'
import FindingCard from './components/FindingCard.jsx'
import PlaybookPanel from './components/PlaybookPanel.jsx'
import SummaryBar from './components/SummaryBar.jsx'

// Findings are grouped by what the reviewer should do with them, not by clause
// order: the things a human must decide come first.
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

export default function App() {
  const [contractText, setContractText] = useState('')
  const [samples, setSamples] = useState(null)
  const [rules, setRules] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [isReviewing, setIsReviewing] = useState(false)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    getSamples()
      .then((data) => {
        setSamples(data)
        setContractText(data.sample_contract)
      })
      .catch((err) => setError(err.message))

    getPlaybook().then(setRules).catch(() => {})
    getHealth().then(setHealth).catch(() => {})
  }, [])

  async function handleReview() {
    setIsReviewing(true)
    setError('')
    setResult(null)

    try {
      setResult(await reviewContract(contractText))
    } catch (err) {
      setError(err.message)
    } finally {
      setIsReviewing(false)
    }
  }

  const findings = result?.findings ?? []

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1>Zycus Redlining Agent</h1>
          <p className="app__subtitle">
            Reviews a counterparty contract against the Zycus playbook, proposes redline
            language, and separates what it can verify from what a human should judge.
          </p>
        </div>
      </header>

      {health && !health.llm_configured && (
        <div className="alert alert--warning">
          No API key is configured on the server, so reviews cannot run. Set
          OPENAI_API_KEY and restart.
        </div>
      )}

      <main className="app__main">
        <PlaybookPanel rules={rules} />

        <ContractInput
          value={contractText}
          onChange={setContractText}
          onReview={handleReview}
          onLoadSample={() => samples && setContractText(samples.sample_contract)}
          onLoadAmbiguous={() => samples && setContractText(samples.ambiguous_contract)}
          isReviewing={isReviewing}
        />

        {error && <div className="alert alert--error">{error}</div>}

        {isReviewing && (
          <div className="progress">
            <div className="progress__bar" />
            <p>
              Segmenting clauses, matching playbook rules, checking thresholds and drafting
              redlines…
            </p>
          </div>
        )}

        {result && (
          <>
            <SummaryBar summary={result.summary} />

            {GROUPS.map((group) => {
              const groupFindings = findings.filter(group.match)
              if (!groupFindings.length) return null

              return (
                <section key={group.id} className={`group group--${group.id}`}>
                  <div className="group__header">
                    <h2>
                      {group.title}
                      <span className="group__count">{groupFindings.length}</span>
                    </h2>
                    <p>{group.blurb}</p>
                  </div>
                  <div className="group__items">
                    {groupFindings.map((finding) => (
                      <FindingCard
                        key={`${finding.clause_number}-${finding.rule_id ?? 'none'}`}
                        finding={finding}
                      />
                    ))}
                  </div>
                </section>
              )
            })}
          </>
        )}
      </main>

      <footer className="app__footer">
        Deterministic checks run in Python before any model call, so threshold findings are
        arithmetic rather than model judgment.
      </footer>
    </div>
  )
}
