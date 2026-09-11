import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { useAuth } from '../Auth'
import type { DocListing } from '../types'

export function Photos() {
  const { user } = useAuth()
  const [listing, setListing] = useState<DocListing | null>(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')

  const load = async () => setListing(await api<DocListing>('/api/photos'))

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not open photos.'))
  }, [])

  const upload = async (files: FileList | null) => {
    if (!files?.length || !user) return
    const body = new FormData()
    body.set('csrf', user.csrf)
    Array.from(files).forEach((f) => body.append('files', f))
    try {
      const result = await api<{ saved: number }>('/api/photos', { method: 'POST', body })
      setOk(`${result.saved} photo${result.saved === 1 ? '' : 's'} saved.`)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save those pictures.')
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Add photos</h1>
          <p className="muted">Pick as many pictures as you want. They go into Documents → Teacher photos.</p>
        </div>
        <Link className="btn" to="/documents">Open folder</Link>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {ok ? <div className="status status--ok">{ok}</div> : null}
      <section className="panel">
        <label className="field">
          <span className="field__label">Pictures</span>
          <input className="input" type="file" accept="image/*" multiple onChange={(e) => void upload(e.target.files)} />
        </label>
      </section>
      <h2>Already in Teacher photos</h2>
      <div className="card-grid">
        {(listing?.files || []).map((f) => (
          <article key={f.rel} className="item-card">
            <h3 className="wrap-any">{f.label}</h3>
            <p className="muted">{f.size_label}</p>
            {f.inline_href ? <a href={f.inline_href} target="_blank" rel="noreferrer">Open</a> : null}
          </article>
        ))}
      </div>
    </>
  )
}
