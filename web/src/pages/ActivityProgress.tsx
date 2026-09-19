import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { useAuth } from '../Auth'

type HardItem = {
  id: string
  name: string
  capital: string
  seen: number
  correct: number
  wrong: number
  miss_rate: number
}

type StudentRow = {
  student_id: number
  name: string
  activities: { activity_id: string; hard: HardItem[] }[]
}

function HardList({ items }: { items: HardItem[] }) {
  if (!items.length) return <p className="muted">Nothing is stuck yet. Play a few rounds and this fills in.</p>
  return (
    <ul className="plain-list struggle-list">
      {items.map((item) => (
        <li key={item.id}>
          <strong className="wrap-any">{item.name}</strong>
          <span className="muted wrap-any">
            {item.capital} · missed {item.wrong} of {item.seen} ({Math.round(item.miss_rate)}%)
          </span>
        </li>
      ))}
    </ul>
  )
}

export function ActivityProgress() {
  const { user } = useAuth()
  const [students, setStudents] = useState<StudentRow[]>([])
  const [mine, setMine] = useState<HardItem[]>([])
  const [strong, setStrong] = useState<HardItem[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api<{ students: StudentRow[] }>('/api/activities/struggle?activity_id=us-state-capitals')
      .then((d) => setStudents(d.students || []))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load the report.'))
    api<{ need_work: HardItem[]; strong: HardItem[] }>('/api/activities/us-state-capitals/struggle')
      .then((d) => {
        setMine(d.need_work || [])
        setStrong(d.strong || [])
      })
      .catch(() => undefined)
  }, [])

  return (
    <>
      <header className="page-head">
        <div>
          <h1>What needs work</h1>
          <p className="muted">
            States and capitals that keep getting missed. Short daily practice on these beats cramming all 50.
          </p>
        </div>
        <p>
          <Link to="/activities/state-capitals" className="btn btn--primary">Practice the hard ones</Link>
        </p>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <section className="panel">
        <h2>{user?.is_teacher ? 'Your view' : 'Your sticky spots'}</h2>
        <HardList items={mine} />
        {strong.length ? (
          <>
            <h3>Getting solid</h3>
            <p className="muted">Seen at least three times with almost no misses.</p>
            <HardList items={strong} />
          </>
        ) : null}
      </section>
      {user?.is_teacher ? (
        <section className="panel">
          <h2>How the family is doing</h2>
          {students.map((row) => (
            <div key={row.student_id} className="struggle-student">
              <h3 className="wrap-any">{row.name}</h3>
              {row.activities.length ? row.activities.map((act) => (
                <HardList key={act.activity_id} items={act.hard} />
              )) : <p className="muted">No misses recorded yet.</p>}
            </div>
          ))}
        </section>
      ) : null}
    </>
  )
}
