import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Confirm } from '../ui/Confirm'

type KeyRow = { id: number; name: string; provider: string }

export function Settings() {
  const { user, me, setLook, refresh } = useAuth()
  const [keys, setKeys] = useState<KeyRow[]>([])
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('openai')
  const [secret, setSecret] = useState('')
  const [error, setError] = useState('')
  const [drop, setDrop] = useState<KeyRow | null>(null)
  const [phone, setPhone] = useState(user?.phone || '')
  const [phoneOk, setPhoneOk] = useState('')
  const [nickname, setNickname] = useState(user?.nickname || '')
  const [soundOn, setSoundOn] = useState(user?.sound_enabled !== false)
  const [profileOk, setProfileOk] = useState('')

  const load = async () => {
    if (!user?.can_use_ai) return
    const data = await api<{ keys: KeyRow[] }>('/api/keys')
    setKeys(data.keys)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load keys.'))
  }, [])

  const addKey = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    try {
      await postJson('/api/keys', { name, provider, secret, csrf: user.csrf })
      setName('')
      setSecret('')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save that key.')
    }
  }

  if (!user) return null

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Profile</h1>
          <p className="muted wrap-any">
            {user.full_name} · {user.email}
          </p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <section className="panel">
        <h2>What we call you</h2>
        <form className="form form--grid" onSubmit={(e) => {
          e.preventDefault()
          void postJson('/api/profile', { nickname, sound_enabled: soundOn, csrf: user.csrf }).then(() => {
            setProfileOk('Saved.')
            void refresh()
          })
        }}>
          <label className="field">
            <span className="field__label">Nickname</span>
            <input className="input" value={nickname} onChange={(e) => setNickname(e.target.value)} placeholder="Greg" />
          </label>
          <label className="check">
            <input type="checkbox" checked={soundOn} onChange={(e) => setSoundOn(e.target.checked)} />
            Play sounds in activities
          </label>
          <div className="field"><button type="submit" className="btn btn--primary">Save</button></div>
        </form>
        {profileOk ? <p className="muted">{profileOk}</p> : null}
      </section>
      <section className="panel">
        <h2>Phone for texts</h2>
        <p className="muted">T-Mobile number, 10 digits. Reminders can text this phone.</p>
        <form className="form form--grid" onSubmit={(e) => {
          e.preventDefault()
          void postJson('/api/profile/phone', { phone, csrf: user.csrf }).then(() => setPhoneOk('Phone saved.'))
        }}>
          <label className="field">
            <span className="field__label">Phone</span>
            <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="9195551234" />
          </label>
          <div className="field"><button type="submit" className="btn btn--primary">Save phone</button></div>
        </form>
        {phoneOk ? <p className="muted">{phoneOk}</p> : null}
      </section>
      <section className="panel">
        <h2>How the site looks</h2>
        <p className="field__label">Colors</p>
        <div className="theme-picks">
          {(me?.themes || []).map((item) => (
            <button
              key={item}
              type="button"
              className={`theme-pick ${user.theme === item ? 'is-on' : ''}`}
              data-theme-preview={item}
              onClick={() => void setLook(item, user.density)}
            >
              {me?.theme_labels?.[item] || item}
            </button>
          ))}
        </div>
        <p className="field__label">Size</p>
        <div className="theme-picks">
          {(me?.densities || []).map((item) => (
            <button
              key={item}
              type="button"
              className={`btn ${user.density === item ? 'btn--primary' : ''}`}
              onClick={() => void setLook(user.theme, item)}
            >
              {me?.density_labels?.[item] || item}
            </button>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>Password</h2>
        <p>
          <Link className="btn" to="/password">Change password</Link>
        </p>
      </section>
      {user.can_use_ai ? (
        <section className="panel">
          <h2>My keys</h2>
          <p className="muted">Name them so you know which is which. We keep the secret hidden.</p>
          <ul className="plain-list">
            {keys.map((k) => (
              <li key={k.id}>
                <strong className="wrap-any">{k.name}</strong>
                <span className="muted">{k.provider}</span>
                <button type="button" className="linkish" onClick={() => setDrop(k)}>Remove</button>
              </li>
            ))}
          </ul>
          <form className="form" onSubmit={(e) => void addKey(e)}>
            <label className="field">
              <span className="field__label">Name</span>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Joe OpenAI" />
            </label>
            <label className="field">
              <span className="field__label">Kind</span>
              <select className="input" value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </label>
            <label className="field">
              <span className="field__label">Secret</span>
              <input className="input" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} required />
            </label>
            <button type="submit" className="btn btn--primary">Save key</button>
          </form>
        </section>
      ) : null}
      {drop ? (
        <Confirm
          title="Remove this key?"
          message={drop.name}
          confirmLabel="Remove"
          onCancel={() => setDrop(null)}
          onConfirm={() => {
            void postJson(`/api/keys/${drop.id}/delete`, { csrf: user.csrf }).then(() => {
              setDrop(null)
              void load()
            })
          }}
        />
      ) : null}
    </>
  )
}
