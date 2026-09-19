import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api'
import { useAuth } from '../Auth'
import { BrandMark } from '../ui/BrandMark'

export function Choose() {
  const { user, loading, me } = useAuth()
  if (loading) return null
  if (user?.must_change_password) return <Navigate to="/password" replace />
  if (user) return <Navigate to={user.is_teacher ? '/teacher' : '/activities'} replace />
  return (
    <div className="gate-page">
      <div className="gate">
        <span className="brand__mark brand__mark--gate">
          <BrandMark />
        </span>
        <p className="eyebrow">Homeschool</p>
        <h1>{me?.site_name || 'Ascendancy Academy'}</h1>
        <p className="brand__tag brand__tag--gate">Ascend above the standards.</p>
        <p className="lede">Two doors. Pick the one that is yours.</p>
        <div className="door-grid">
          <Link className="door-card" to="/login/teacher">
            <span>Adults</span>
            <strong>I am a teacher</strong>
            <span>Mark attendance, enter grades, print calendars.</span>
          </Link>
          <Link className="door-card door-card--student" to="/login/student">
            <span>Student</span>
            <strong>I am Gregory</strong>
            <span>See what’s due, grades, and the calendar.</span>
          </Link>
        </div>
      </div>
    </div>
  )
}

export function Login() {
  const { door } = useParams()
  const { user, loading, login, me } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [turnstile, setTurnstile] = useState('')
  const siteKey = me?.turnstile.enabled && me.turnstile.site_key ? me.turnstile.site_key : ''

  useEffect(() => {
    if (!siteKey) return
    const box = document.getElementById('cf-box')
    const w = window as unknown as {
      turnstile?: { render: (el: HTMLElement, opts: Record<string, unknown>) => void }
    }
    const render = () => {
      if (box && w.turnstile) {
        box.innerHTML = ''
        w.turnstile.render(box, {
          sitekey: siteKey,
          theme: 'auto',
          callback: (token: string) => setTurnstile(token),
        })
      }
    }
    if (w.turnstile) {
      render()
      return
    }
    const script = document.createElement('script')
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
    script.async = true
    script.onload = render
    document.body.appendChild(script)
  }, [siteKey])
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next') || ''
  const side = door === 'student' ? 'student' : 'teacher'

  if (loading) return null
  if (user?.must_change_password) return <Navigate to="/password" replace />
  if (user) return <Navigate to={user.is_teacher ? '/teacher' : '/activities'} replace />

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const dest = await login(side, email, password, turnstile)
      navigate(next.startsWith('/') ? next : dest)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in.')
    }
  }

  return (
    <div className="gate-page">
      <div className="gate gate--narrow">
        <p className="eyebrow">{side === 'teacher' ? 'Teacher' : 'Student'} door</p>
        <h1>Sign in</h1>
        <p className="lede">
          {side === 'teacher' ? 'For Joe and Kim DiFede.' : 'For Gregory.'}{' '}
          <Link to={side === 'teacher' ? '/login/student' : '/login/teacher'}>Wrong door?</Link>
        </p>
        {error ? <div className="status status--error">{error}</div> : null}
        <form className="form" onSubmit={(e) => void onSubmit(e)}>
          <label className="field">
            <span className="field__label">Email</span>
            <input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field">
            <span className="field__label">Password</span>
            <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {siteKey ? <div id="cf-box" className="turnstile-wrap" /> : null}
          <button type="submit" className="btn btn--primary btn--block">
            Sign in
          </button>
        </form>
      </div>
    </div>
  )
}
