import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { Modal } from '../ui/Modal'
import type { AttemptDetail } from '../types'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

type ResultRow = {
  attempt_id: number
  test_id: number
  test_title: string
  student_name: string
  attempt_no: number
  score_points: number
  score_possible: number
  percent: number | null
  allow_retries: boolean
  submitted_at: string
}

export function TestResults() {
  const [rows, setRows] = useState<ResultRow[]>([])
  const [error, setError] = useState('')
  const [detail, setDetail] = useState<AttemptDetail | null>(null)

  useEffect(() => {
    api<{ results: ResultRow[] }>('/api/tests/results/all')
      .then((d) => setRows(d.results))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load results.'))
  }, [])

  const open = (attemptId: number) => {
    api<AttemptDetail>(`/api/tests/attempts/${attemptId}`)
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load that attempt.'))
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Test results</h1>
          <p className="muted">Every attempt your students turned in.</p>
        </div>
        <Link to="/tests" className="btn btn--ghost">Back to Test Maker</Link>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <div className="table-wrap">
        <table className="sheet">
          <thead>
            <tr><th>Student</th><th>Test</th><th>Try</th><th>Score</th><th>When</th><th /></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.attempt_id}>
                <td className="wrap-text">{r.student_name}</td>
                <td className="wrap-text">{r.test_title}</td>
                <td>{r.attempt_no}</td>
                <td>{r.percent != null ? `${r.percent}%` : '—'} <span className="muted">({r.score_points}/{r.score_possible})</span></td>
                <td>{r.submitted_at.slice(0, 16).replace('T', ' ')}</td>
                <td><button type="button" className="btn btn--small" onClick={() => open(r.attempt_id)}>View</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 ? <p className="muted">No attempts yet.</p> : null}
      </div>

      {detail ? (
        <Modal title={`${detail.attempt.test_title} — attempt ${detail.attempt.attempt_no}`} onClose={() => setDetail(null)}>
          <p className="grade-big">{detail.attempt.percent != null ? `${detail.attempt.percent}%` : '—'} <span className="muted">{detail.attempt.score_points}/{detail.attempt.score_possible}</span></p>
          {detail.questions.map((q, i) => (
            <div key={q.id} className={`q-review ${q.is_correct ? 'is-right' : 'is-wrong'}`}>
              <p><strong>{i + 1}.</strong> {q.prompt} <span className="muted">({q.points_earned}/{q.points}){q.retried ? ' · retried' : ''}</span></p>
              <AnswerKey q={q} />
              {q.explanation ? <p className="muted">Why: {q.explanation}</p> : null}
            </div>
          ))}
        </Modal>
      ) : null}
    </>
  )
}

function AnswerKey({ q }: { q: AttemptDetail['questions'][number] }) {
  if (q.type === 'mc') {
    const correct = (q.options || []).filter((o) => (q.correct || []).includes(o.id)).map((o) => o.text)
    return <p className="muted">Answer: {correct.join(', ')}</p>
  }
  if (q.type === 'tf') return <p className="muted">Answer: {q.answer ? 'True' : 'False'}</p>
  if (q.type === 'match') {
    return (
      <p className="muted">
        Answer: {(q.left || []).map((l, i) => {
          const rid = (q.pairs || {})[l.id]
          const r = (q.right || []).find((x) => x.id === rid)
          const ri = (q.right || []).findIndex((x) => x.id === rid)
          return `${i + 1}→${ri >= 0 ? LETTERS[ri] : '?'}${r ? ` (${r.text})` : ''}`
        }).join('   ')}
      </p>
    )
  }
  return <p className="muted">Answer: {(q.accepted || []).join(' / ')}</p>
}
