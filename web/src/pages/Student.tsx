import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { Board } from '../ui/Board'
import type { AssignedTest, Course, Totals } from '../types'

type Home = {
  student: { id: number; name: string } | null
  totals: Totals | null
  courses: Course[]
  due: { title: string; course: string; due: string }[]
  recent: { title: string; earned: number; possible: number | null }[]
}

type GradeRow = {
  course: Course
  result: { percent: number | null; letter: string | null }
  assignments: { id: number; title: string; due: string; points_possible: number; earned: number | null }[]
}

export function StudentHome() {
  const [data, setData] = useState<Home | null>(null)
  const [tests, setTests] = useState<AssignedTest[]>([])
  const [acts, setActs] = useState<{ activity_id: string; title: string; best_stars?: number; best_accuracy?: number; plays?: number }[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api<Home>('/api/student')
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load home.'))
    api<{ tests: AssignedTest[] }>('/api/tests/student/assigned')
      .then((d) => setTests(d.tests))
      .catch(() => undefined)
    api<{ activities: { activity_id: string; title: string; best_stars?: number; best_accuracy?: number; plays?: number }[] }>('/api/activities')
      .then((d) => setActs(d.activities))
      .catch(() => undefined)
  }, [])

  if (!data) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Hi, {data.student?.name}.</h1>
          <p className="muted">Here is what matters today.</p>
        </div>
      </header>
      <Board />
      {acts.length ? (
        <section className="panel">
          <h2>Practice</h2>
          <ul className="plain-list">
            {acts.map((a) => (
              <li key={a.activity_id}>
                <Link to={a.activity_id === 'us-state-capitals' ? '/activities/state-capitals' : '/activities'}>
                  <span className="wrap-any">{a.title}</span>
                </Link>
                <span className="muted">
                  {a.plays ? `Played ${a.plays}` : 'Not played yet'}
                  {a.best_accuracy ? ` · best ${Math.round(a.best_accuracy)}%` : ''}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {tests.length ? (
        <section className="panel">
          <h2>Tests to take</h2>
          <ul className="plain-list">
            {tests.map((t) => (
              <li key={t.id}>
                <span className="wrap-any">{t.title} <span className="muted">{t.course_title} · {t.question_count} questions</span></span>
                {t.status === 'graded' ? (
                  <span className="muted">
                    {t.percent != null ? `${t.percent}%` : 'Done'}
                    {t.can_retry ? <> · <Link to={`/take/${t.id}`}>fix misses</Link></> : null}
                  </span>
                ) : (
                  <Link to={`/take/${t.id}`} className="btn btn--small btn--primary">Start</Link>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {data.totals ? (
        <section className="stat-row">
          <div className="stat"><strong>{data.totals.present}</strong><span>Days present</span></div>
          <div className="stat"><strong>{data.totals.remaining}</strong><span>Days to {data.totals.target}</span></div>
          <div className="stat"><strong>{data.totals.absent}</strong><span>Absent</span></div>
        </section>
      ) : null}
      <div className="split">
        <section className="panel">
          <h2>Due soon</h2>
          {data.due.length ? (
            <ul className="plain-list">
              {data.due.map((item) => (
                <li key={`${item.title}-${item.due}`}>
                  <span className="wrap-any">{item.title}</span>
                  <span className="muted">{item.course} · {item.due}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing is due right now.</p>
          )}
        </section>
        <section className="panel">
          <h2>Recent scores</h2>
          {data.recent.length ? (
            <ul className="plain-list">
              {data.recent.map((g) => (
                <li key={g.title}>
                  <span className="wrap-any">{g.title}</span>
                  <span className="muted">{g.earned} / {g.possible ?? '—'}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No scores yet.</p>
          )}
          <p><Link to="/grades">See all grades</Link></p>
        </section>
      </div>
      <section className="card-grid">
        {data.courses.map((c) => (
          <article key={c.id} className="class-card" style={{ '--course': c.color } as CSSProperties}>
            <h2 className="wrap-any">{c.title}</h2>
            {c.student_brief ? <p className="muted wrap-any">{c.student_brief}</p> : null}
            {c.schedule ? <p className="muted">{c.schedule}{c.location ? ` · ${c.location}` : ''}</p> : null}
            <p className="grade-big">
              {c.letter || '—'} {c.percent != null ? <span>{c.percent}%</span> : null}
            </p>
          </article>
        ))}
      </section>
    </>
  )
}

export function StudentGrades() {
  const [rows, setRows] = useState<GradeRow[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api<{ rows: GradeRow[] }>('/api/student/grades')
      .then((data) => setRows(data.rows))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load grades.'))
  }, [])

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Grades</h1>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {rows.map((row) => (
        <section key={row.course.id} className="panel">
          <div className="panel__head">
            <h2 className="wrap-any">{row.course.title}</h2>
            <p className="grade-big">
              {row.result.letter || '—'} {row.result.percent != null ? <span>{row.result.percent}%</span> : null}
            </p>
          </div>
          {row.course.student_brief ? <p className="muted wrap-any">{row.course.student_brief}</p> : null}
          {row.course.schedule || row.course.location ? (
            <p className="muted">{[row.course.schedule, row.course.location].filter(Boolean).join(' · ')}</p>
          ) : null}
          {row.course.materials ? <p className="muted wrap-any">Bring: {row.course.materials}</p> : null}
          <div className="table-wrap">
            <table className="sheet">
              <thead>
                <tr><th>Work</th><th>Due</th><th>Score</th></tr>
              </thead>
              <tbody>
                {row.assignments.map((a) => (
                  <tr key={a.id}>
                    <td className="wrap-text">{a.title}</td>
                    <td>{a.due || '—'}</td>
                    <td>{a.earned != null ? `${a.earned} / ${a.points_possible}` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </>
  )
}
