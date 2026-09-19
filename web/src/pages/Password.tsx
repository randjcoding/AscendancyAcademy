import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { ApiError, postJson } from '../api'
import { useAuth } from '../Auth'

export function Password() {
  const { user, loading, refresh } = useAuth()
  const [current, setCurrent] = useState('')
  const [nextPw, setNextPw] = useState('')
  const [again, setAgain] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const forced = Boolean(user?.must_change_password)

  if (loading) return null
  if (!user) return <Navigate to="/" replace />

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await postJson('/api/password', {
        current_password: current,
        new_password: nextPw,
        confirm_password: again,
        csrf: user.csrf,
        forced,
      })
      await refresh()
      navigate(user.is_teacher ? '/teacher' : '/activities')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save that password.')
    }
  }

  return (
    <div className="gate-page">
      <div className="gate gate--narrow">
        <p className="eyebrow">{forced ? 'First visit' : 'Account'}</p>
        <h1>Choose a new password</h1>
        <p className="lede">At least 10 characters. You will stay signed in after this.</p>
        {error ? <div className="status status--error">{error}</div> : null}
        <form className="form" onSubmit={(e) => void onSubmit(e)}>
          {!forced ? (
            <label className="field">
              <span className="field__label">Current password</span>
              <input className="input" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
            </label>
          ) : null}
          <label className="field">
            <span className="field__label">New password</span>
            <input className="input" type="password" autoComplete="new-password" required minLength={10} value={nextPw} onChange={(e) => setNextPw(e.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Type it again</span>
            <input className="input" type="password" autoComplete="new-password" required minLength={10} value={again} onChange={(e) => setAgain(e.target.value)} />
          </label>
          <button type="submit" className="btn btn--primary btn--block">
            Save password
          </button>
        </form>
      </div>
    </div>
  )
}
