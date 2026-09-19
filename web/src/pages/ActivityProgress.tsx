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
  const [paths, setPaths] = useState<{ student_id: number; name: string; path: { beaten: boolean; regions: { label: string; passed: boolean; unlocked: boolean }[] } }[]>([])
  const [myPath, setMyPath] = useState<{ beaten: boolean; regions: { label: string; passed: boolean; unlocked: boolean; intro_done: boolean }[]; final_open: boolean } | null>(null)

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
    api<{ path: { beaten: boolean; regions: { label: string; passed: boolean; unlocked: boolean; intro_done: boolean }[]; final_open: boolean } | null }>('/api/activities/us-state-capitals/path')
      .then((d) => setMyPath(d.path))
      .catch(() => undefined)
    if (user?.is_teacher) {
      api<{ students: { student_id: number; name: string; path: { beaten: boolean; regions: { label: string; passed: boolean; unlocked: boolean }[] } }[] }>('/api/activities/us-state-capitals/paths')
        .then((d) => setPaths(d.students || []))
        .catch(() => undefined)
    }
  }, [user?.is_teacher])

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
      {myPath ? (
        <section className="panel">
          <h2>Learn the country</h2>
          <p className="muted">{myPath.beaten ? 'The whole country is done.' : myPath.final_open ? 'Groups are done. Beat the country next.' : 'Work one group at a time to 90%.'}</p>
          <ul className="plain-list">
            {myPath.regions.map((r) => (
              <li key={r.label}>
                <strong className="wrap-any">{r.label}</strong>
                <span className="muted">{r.passed ? 'Done' : r.unlocked ? (r.intro_done ? 'In progress' : 'Say the names') : 'Locked'}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
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
      {user?.is_teacher && paths.length ? (
        <section className="panel">
          <h2>Path by student</h2>
          {paths.map((row) => (
            <p key={row.student_id}>
              <strong className="wrap-any">{row.name}</strong>
              <span className="muted">
                {' '}
                {row.path.beaten ? 'Beat the country' : row.path.regions.filter((r) => r.passed).map((r) => r.label).join(', ') || 'Just starting'}
              </span>
            </p>
          ))}
        </section>
      ) : null}
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
