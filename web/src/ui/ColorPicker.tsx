import { useEffect, useState } from 'react'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import type { ColorOpt } from '../types'
import { Confirm } from './Confirm'

type EyeDropperCtor = new () => { open: () => Promise<{ sRGBHex: string }> }

function asHex(value: string) {
  if (value.startsWith('#') && (value.length === 7 || value.length === 4)) return value
  return '#2D6A4F'
}

export function ColorPicker({ value, onChange }: { value: string; onChange: (hex: string) => void }) {
  const { user } = useAuth()
  const [hex, setHex] = useState(asHex(value))
  const [name, setName] = useState('')
  const [query, setQuery] = useState('')
  const [saved, setSaved] = useState<ColorOpt[]>([])
  const [error, setError] = useState('')
  const [drop, setDrop] = useState<ColorOpt | null>(null)
  const canDrop = typeof window !== 'undefined' && 'EyeDropper' in window

  const load = async (q = query) => {
    const data = await api<{ colors: ColorOpt[] }>(`/api/colors?q=${encodeURIComponent(q)}`)
    setSaved(data.colors)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load saved colors.'))
  }, [])

  const pick = (next: string) => {
    const clean = asHex(next)
    setHex(clean)
    onChange(clean)
  }

  const eyedrop = async () => {
    const Ctor = (window as unknown as { EyeDropper?: EyeDropperCtor }).EyeDropper
    if (!Ctor) return
    try {
      pick((await new Ctor().open()).sRGBHex)
    } catch {
      /* cancelled */
    }
  }

  const save = async () => {
    if (!user) return
    setError('')
    try {
      await postJson('/api/colors', { name, hex, csrf: user.csrf })
      setName('')
      await load(query)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save that color.')
    }
  }

  return (
    <div className="color-picker">
      <div className="color-picker__custom">
        <label className="field">
          <span className="field__label">Color</span>
          <input type="color" value={hex} onChange={(e) => pick(e.target.value)} />
        </label>
        {canDrop ? (
          <button type="button" className="btn" onClick={() => void eyedrop()}>
            Eyedropper
          </button>
        ) : null}
      </div>
      <div className="color-picker__save">
        <label className="field">
          <span className="field__label">Save as</span>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ELA green"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                void save()
              }
            }}
          />
        </label>
        <button type="button" className="btn" disabled={!name.trim()} onClick={() => void save()}>
          Save color
        </button>
      </div>
      {error ? <p className="muted">{error}</p> : null}
      <label className="field">
        <span className="field__label">Find a saved color</span>
        <input
          className="input"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            void load(e.target.value)
          }}
          placeholder="Search by name"
          onKeyDown={(e) => {
            if (e.key === 'Enter') e.preventDefault()
          }}
        />
      </label>
      <div className="color-saved">
        {saved.map((c) => (
          <div key={c.id || c.name} className="color-saved__row">
            <button type="button" className="color-saved__pick" onClick={() => pick(c.hex)}>
              <span className="color-swatch__chip" style={{ background: c.hex }} />
              <span className="wrap-any">{c.name}</span>
            </button>
            <button type="button" className="linkish" onClick={() => setDrop(c)}>
              Remove
            </button>
          </div>
        ))}
        {!saved.length ? <p className="muted">No saved colors yet. Pick one and give it a name.</p> : null}
      </div>
      {drop && user ? (
        <Confirm
          title="Remove this color?"
          message={drop.name}
          confirmLabel="Remove"
          onCancel={() => setDrop(null)}
          onConfirm={() => {
            void postJson(`/api/colors/${drop.id}/delete`, { csrf: user.csrf }).then(() => {
              setDrop(null)
              void load(query)
            })
          }}
        />
      ) : null}
    </div>
  )
}
