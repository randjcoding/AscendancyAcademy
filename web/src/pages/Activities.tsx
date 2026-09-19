import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ApiError } from '../api'
import { useAuth } from '../Auth'
import { Stars } from '../activities/DrillHud'

type Card = {
  activity_id: string
  title: string
  category: string
  icon: string
  type: string
  item_count: number
  best_stars?: number
  best_accuracy?: number
  plays?: number
  streak?: number
}

type ResultRow = {
  student_id: number
  name: string
  streak: number
  activities: { activity_id: string; best_stars: number; best_accuracy: number; plays: number; hard?: { name: string }[] }[]
}

export function Activities() {
  const { user } = useAuth()
  const [cards, setCards] = useState<Card[]>([])
  const [streak, setStreak] = useState(0)
  const [results, setResults] = useState<ResultRow[]>([])
  const [history, setHistory] = useState<{ accuracy: number; when: string }[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api<{ activities: Card[]; streak: number }>('/api/activities')
      .then((d) => {
        setCards(d.activities)
        setStreak(d.streak)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load activities.'))
    api<{ history: { accuracy: number; when: string }[] }>('/api/activities/us-state-capitals/history')
      .then((d) => setHistory(d.history.slice().reverse().filter((h) => h.accuracy > 0)))
      .catch(() => undefined)
    if (user?.is_teacher) {
      api<{ results: ResultRow[] }>('/api/activities/results')
        .then((d) => setResults(d.results))
        .catch(() => undefined)
    }
  }, [user?.is_teacher])

  const hrefFor = (id: string) => (id === 'us-state-capitals' ? '/activities/state-capitals' : `/activities/${id}`)

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Activities</h1>
          <p className="muted">Practice until it sticks. Stars stay with you.</p>
        </div>
        <div className="btn-row">
          {streak ? <p className="streak-chip">{streak} day streak</p> : null}
          <Link to="/activities/progress" className="btn">What needs work</Link>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <section className="card-grid">
        {cards.map((c) => (
          <Link key={c.activity_id} to={hrefFor(c.activity_id)} className="activity-card">
            <p className="muted">{c.category}</p>
            <h2 className="wrap-any">{c.title}</h2>
            <Stars count={c.best_stars || 0} />
            <p className="muted">
              {c.item_count} items{c.plays ? ` · played ${c.plays}` : ''}
              {c.best_accuracy ? ` · best ${Math.round(c.best_accuracy)}%` : ''}
            </p>
          </Link>
        ))}
      </section>
      {history.length > 1 ? (
        <section className="panel">
          <h2>Accuracy over time</h2>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={history}>
                <XAxis dataKey="when" hide />
                <YAxis domain={[0, 100]} width={32} />
                <Tooltip />
                <Line type="monotone" dataKey="accuracy" stroke="var(--brand)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
      {user?.is_teacher && results.length ? (
        <section className="panel">
          <h2>How they are doing</h2>
          <ul className="plain-list">
            {results.map((r) => (
              <li key={r.student_id}>
                <strong className="wrap-any">{r.name}</strong>
                <span className="muted">
                  {r.streak ? `${r.streak} day streak · ` : ''}
                  {r.activities.map((a) => {
                    const hard = a.hard || []
                    return `${a.activity_id}: ${a.best_stars}★${hard.length ? ` · needs work: ${hard.slice(0, 4).map((h) => h.name).join(', ')}` : ''}`
                  }).join(' · ') || 'No plays yet'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  )
}
