import { useEffect, useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'

const PURPOSES = [
  { id: 'read_pages', label: 'Read pages (photos)' },
  { id: 'make_test', label: 'Make tests' },
]

type Person = {
  id: number
  name: string
  full_name: string
  nickname: string
  email: string
  role: string
  kind: string
  ai_grants: string[]
}

type Snap = { student_id: number; name: string; streak: number; activities: { activity_id: string; best_stars: number }[] }

export function Admin() {
  const { user } = useAuth()
  const [people, setPeople] = useState<Person[]>([])
  const [snap, setSnap] = useState<Snap[]>([])
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [email, setEmail] = useState('')
  const [first, setFirst] = useState('')
  const [last, setLast] = useState('')
  const [nick, setNick] = useState('')
  const [kind, setKind] = useState('student')
  const [password, setPassword] = useState('')

  const load = () => {
    api<{ people: Person[] }>('/api/admin/people')
      .then((d) => setPeople(d.people))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load admin.'))
    api<{ results: Snap[] }>('/api/admin/activities')
      .then((d) => setSnap(d.results))
      .catch(() => undefined)
  }

  useEffect(() => {
    if (user?.is_super_admin) load()
  }, [user?.is_super_admin])

  if (user && !user.is_super_admin) return <Navigate to="/teacher" replace />
  if (!user) return null

  const toggle = async (person: Person, purpose: string) => {
    const allowed = !person.ai_grants.includes(purpose)
    try {
      await postJson('/api/admin/ai-grant', { csrf: user.csrf, user_id: person.id, purpose, allowed })
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not change that grant.')
    }
  }

  const add = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await postJson('/api/admin/people', {
        csrf: user.csrf,
        email,
        first_name: first,
        last_name: last,
        nickname: nick,
        kind,
        password,
      })
      setOk('Person added. They will pick a new password at sign-in.')
      setEmail('')
      setFirst('')
      setLast('')
      setNick('')
      setPassword('')
      load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add that person.')
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Admin</h1>
          <p className="muted">Joe only. People, AI uses, and activity stars.</p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {ok ? <div className="status status--ok">{ok}</div> : null}

      <section className="panel">
        <h2>Add a person</h2>
        <form className="form form--grid" onSubmit={(e) => void add(e)}>
          <label className="field"><span>Email</span><input required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label className="field"><span>First name</span><input required value={first} onChange={(e) => setFirst(e.target.value)} /></label>
          <label className="field"><span>Last name</span><input value={last} onChange={(e) => setLast(e.target.value)} /></label>
          <label className="field"><span>Nickname</span><input value={nick} onChange={(e) => setNick(e.target.value)} /></label>
          <label className="field">
            <span>Kind</span>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="student">Student</option>
              <option value="teacher">Teacher</option>
            </select>
          </label>
          <label className="field"><span>Temporary password</span><input required minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          <div className="field"><button type="submit" className="btn btn--primary">Add person</button></div>
        </form>
      </section>

      <section className="panel">
        <h2>AI uses</h2>
        <p className="muted">Students stay off until you turn a use on. Teachers already have keys.</p>
        {people.map((p) => (
          <article key={p.id} className="admin-person">
            <div>
              <strong className="wrap-any">{p.name}</strong>
              <p className="muted wrap-any">{p.email} · {p.kind}{p.nickname ? ` · ${p.nickname}` : ''}</p>
            </div>
            {p.kind === 'student' ? (
              <div className="chip-row">
                {PURPOSES.map((g) => (
                  <label key={g.id} className={`chip ${p.ai_grants.includes(g.id) ? 'is-on' : ''}`}>
                    <input type="checkbox" checked={p.ai_grants.includes(g.id)} onChange={() => void toggle(p, g.id)} />
                    {g.label}
                  </label>
                ))}
              </div>
            ) : (
              <p className="muted">Teacher — keys already on.</p>
            )}
          </article>
        ))}
      </section>

      <section className="panel">
        <h2>Activity stars</h2>
        {snap.length ? (
          <ul className="plain-list">
            {snap.map((s) => (
              <li key={s.student_id}>
                <strong className="wrap-any">{s.name}</strong>
                <span className="muted">
                  {s.activities.map((a) => `${a.activity_id} ${a.best_stars}★`).join(' · ') || 'No plays yet'}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No plays yet.</p>
        )}
      </section>
    </>
  )
}
