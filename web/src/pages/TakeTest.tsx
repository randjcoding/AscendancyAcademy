import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import type { AttemptDetail, TestQuestion } from '../types'

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

type TakeTest = {
  id: number
  title: string
  instructions: string
  points_possible: number
  allow_retries: boolean
  retry_credit: 'half' | 'full'
  questions: TestQuestion[]
}

type Responses = Record<number, Record<string, unknown>>

export function TakeTest() {
  const { id } = useParams()
  const { user } = useAuth()
  const csrf = user?.csrf || ''
  const [test, setTest] = useState<TakeTest | null>(null)
  const [responses, setResponses] = useState<Responses>({})
  const [result, setResult] = useState<AttemptDetail | null>(null)
  const [retryResponses, setRetryResponses] = useState<Responses>({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api<{ test: TakeTest }>(`/api/tests/${id}/take`)
      .then((d) => setTest(d.test))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load that test.'))
  }, [id])

  const setResponse = (qid: number, value: Record<string, unknown>) => {
    setResponses((prev) => ({ ...prev, [qid]: value }))
  }

  const submit = async () => {
    if (!test) return
    setError('')
    setBusy(true)
    try {
      const answers = test.questions.map((q) => ({ question_id: q.id, response: responses[q.id] || {} }))
      const res = await postJson<AttemptDetail>(`/api/tests/${id}/submit`, { csrf, answers })
      setResult(res)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not turn in the test.')
    } finally {
      setBusy(false)
    }
  }

  const submitRetry = async () => {
    if (!result) return
    setError('')
    setBusy(true)
    try {
      const wrong = result.questions.filter((q) => !q.first_correct)
      const answers = wrong.map((q) => ({ question_id: q.id, response: retryResponses[q.id] || {} }))
      const res = await postJson<AttemptDetail>(`/api/tests/attempts/${result.attempt.id}/retry`, { csrf, answers })
      setResult(res)
      setRetryResponses({})
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save your fixes.')
    } finally {
      setBusy(false)
    }
  }

  if (!test) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  if (result) {
    const wrong = result.questions.filter((q) => !q.first_correct)
    const creditWord = result.attempt.retry_credit === 'half' ? 'half credit' : 'full credit'
    return (
      <>
        <header className="page-head">
          <div>
            <h1>{result.attempt.test_title}</h1>
            <p className="muted">Attempt {result.attempt.attempt_no}</p>
          </div>
          <Link to="/student" className="btn btn--ghost">Home</Link>
        </header>
        {error ? <div className="status status--error">{error}</div> : null}
        <section className="panel">
          <p className="grade-big">{result.attempt.percent != null ? `${result.attempt.percent}%` : '—'}</p>
          <p className="muted">{result.attempt.score_points} / {result.attempt.score_possible} points</p>
        </section>
        {result.attempt.allow_retries && wrong.length ? (
          <section className="panel">
            <h2>Fix your misses for {creditWord}</h2>
            {wrong.map((q) => (
              <div key={q.id} className="q-take">
                <QuestionTake q={q} value={retryResponses[q.id] || {}} onChange={(v) => setRetryResponses((prev) => ({ ...prev, [q.id]: v }))} />
              </div>
            ))}
            <button type="button" className="btn btn--primary" onClick={() => void submitRetry()} disabled={busy}>Turn in fixes</button>
          </section>
        ) : null}
        <section className="panel">
          <h2>Review</h2>
          {result.questions.map((q, i) => (
            <div key={q.id} className={`q-review ${q.is_correct ? 'is-right' : 'is-wrong'}`}>
              <p><strong>{i + 1}.</strong> {q.prompt} <span className="muted">({q.points_earned} / {q.points})</span></p>
              {q.explanation ? <p className="muted">{q.explanation}</p> : null}
            </div>
          ))}
        </section>
      </>
    )
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>{test.title}</h1>
          {test.instructions ? <p className="muted wrap-any">{test.instructions}</p> : null}
        </div>
        <Link to="/student" className="btn btn--ghost">Home</Link>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <section className="panel">
        {test.questions.map((q, i) => (
          <div key={q.id} className="q-take">
            <p className="q-take__prompt"><strong>{i + 1}.</strong> {q.prompt}</p>
            <QuestionTake q={q} value={responses[q.id] || {}} onChange={(v) => setResponse(q.id, v)} />
          </div>
        ))}
        <button type="button" className="btn btn--primary" onClick={() => void submit()} disabled={busy}>{busy ? 'Turning in…' : 'Turn in test'}</button>
      </section>
    </>
  )
}

function QuestionTake({ q, value, onChange }: { q: TestQuestion; value: Record<string, unknown>; onChange: (v: Record<string, unknown>) => void }) {
  const selected = useMemo(() => (Array.isArray(value.selected) ? (value.selected as string[]) : []), [value.selected])
  const pairs = useMemo(() => (value.pairs && typeof value.pairs === 'object' ? (value.pairs as Record<string, string>) : {}), [value.pairs])

  if (q.type === 'mc') {
    return (
      <div className="q-take__options">
        {(q.options || []).map((o, i) => (
          <label key={o.id} className="q-take__option">
            <input
              type={q.multiple ? 'checkbox' : 'radio'}
              name={`q-${q.id}`}
              checked={selected.includes(o.id)}
              onChange={() => {
                if (q.multiple) onChange({ selected: selected.includes(o.id) ? selected.filter((s) => s !== o.id) : [...selected, o.id] })
                else onChange({ selected: [o.id] })
              }}
            />
            <span className="q-edit__letter">{LETTERS[i]}</span> {o.text}
          </label>
        ))}
      </div>
    )
  }

  if (q.type === 'tf') {
    const ans = value.answer
    return (
      <div className="chip-row">
        <label className={`chip ${ans === true ? 'is-on' : ''}`}><input type="radio" name={`q-${q.id}`} checked={ans === true} onChange={() => onChange({ answer: true })} /> True</label>
        <label className={`chip ${ans === false ? 'is-on' : ''}`}><input type="radio" name={`q-${q.id}`} checked={ans === false} onChange={() => onChange({ answer: false })} /> False</label>
      </div>
    )
  }

  if (q.type === 'match') {
    return (
      <div className="q-edit__match">
        {(q.left || []).map((l, i) => (
          <div key={l.id} className="q-edit__matchrow">
            <span className="q-edit__num">{i + 1}. {l.text}</span>
            <select value={pairs[l.id] || ''} onChange={(e) => onChange({ pairs: { ...pairs, [l.id]: e.target.value } })}>
              <option value="">choose</option>
              {(q.right || []).map((r, ri) => <option key={r.id} value={r.id}>{LETTERS[ri]} · {r.text}</option>)}
            </select>
          </div>
        ))}
      </div>
    )
  }

  // fill
  return (
    <input className="q-take__fill" value={(value.text as string) || ''} onChange={(e) => onChange({ text: e.target.value })} placeholder="Your answer" />
  )
}
