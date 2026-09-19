import { useEffect, useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Modal } from '../ui/Modal'

type Person = { id: number; name: string; nickname: string; email: string; phone: string; role: string; kind: string }

export function People() {
  const { user } = useAuth()
  const [people, setPeople] = useState<Person[]>([])
  const [target, setTarget] = useState<Person | null>(null)
  const [pw, setPw] = useState('')
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

  useEffect(() => {
    if (!user?.can_manage_people) return
    api<{ people: Person[] }>('/api/people')
      .then((data) => setPeople(data.people))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load people.'))
  }, [user])

  if (user && !user.can_manage_people) return <Navigate to="/teacher" replace />

  const reset = async (e: FormEvent) => {
    e.preventDefault()
    if (!user || !target) return
    try {
      await postJson('/api/people/password', { user_id: target.id, new_password: pw, csrf: user.csrf })
      setOk(`${target.name} will change this password next time they sign in.`)
      setTarget(null)
      setPw('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not set that password.')
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>People</h1>
          <p className="muted">Set a temporary password. They must pick a new one at the next sign-in.</p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {ok ? <div className="status status--ok">{ok}</div> : null}
      <div className="card-grid">
        {people.map((p) => (
          <article key={p.id} className="item-card">
            <h3 className="wrap-any">{p.name}</h3>
            {p.nickname ? <p className="muted wrap-any">{p.nickname}</p> : null}
            <p className="muted wrap-any">{p.email}</p>
            <p className="muted">{p.phone || 'No phone yet'}</p>
            <p className="muted">{p.role || p.kind}</p>
            <button type="button" className="btn" onClick={() => setTarget(p)}>
              Reset password
            </button>
          </article>
        ))}
      </div>
      {target ? (
        <Modal title={`New password for ${target.name}`} onClose={() => setTarget(null)}>
          <form className="form" onSubmit={(e) => void reset(e)}>
            <label className="field">
              <span className="field__label">Temporary password</span>
              <input className="input" type="text" minLength={10} required value={pw} onChange={(e) => setPw(e.target.value)} />
            </label>
            <button type="submit" className="btn btn--primary">Save and require a change</button>
          </form>
        </Modal>
      ) : null}
    </>
  )
}
