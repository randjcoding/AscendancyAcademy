import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Confirm } from '../ui/Confirm'

type Reminder = {
  id: number
  name: string
  send_at: string
  audience: string
  status: string
  repeat: string
  repeat_kind: string
  repeat_until: string
  items: { id: number; item_type: string; item_id: number | null; text: string }[]
}

const REPEATS = [
  { id: 'none', label: 'Once' },
  { id: 'hourly', label: 'Hourly' },
  { id: 'daily', label: 'Daily' },
  { id: 'weekdays', label: 'Weekdays' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'biweekly', label: 'Every two weeks' },
  { id: 'monthly', label: 'Monthly' },
  { id: 'yearly', label: 'Yearly' },
]

export function Reminders() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const [rows, setRows] = useState<Reminder[]>([])
  const [canFamily, setCanFamily] = useState(false)
  const [name, setName] = useState('')
  const [when, setWhen] = useState('')
  const [repeat, setRepeat] = useState('none')
  const [until, setUntil] = useState('')
  const [audience, setAudience] = useState('personal')
  const [channel, setChannel] = useState('email')
  const [smsTo, setSmsTo] = useState(user?.phone || '')
  const [note, setNote] = useState('')
  const [taskId, setTaskId] = useState(0)
  const [pageId, setPageId] = useState(0)
  const [tasks, setTasks] = useState<{ id: number; title: string }[]>([])
  const [pages, setPages] = useState<{ id: number; title: string }[]>([])
  const [error, setError] = useState('')
  const [ok, setOk] = useState(params.get('stopped') ? 'That reminder is off.' : '')
  const [drop, setDrop] = useState<Reminder | null>(null)

  const load = async () => {
    const data = await api<{ reminders: Reminder[]; can_family: boolean }>('/api/reminders')
    setRows(data.reminders)
    setCanFamily(data.can_family)
    const taskData = await api<{ tasks: { id: number; title: string }[] }>('/api/tasks')
    setTasks(taskData.tasks.filter((t) => t.title))
    const tree = await api<{ notebooks: { pages: { id: number; title: string }[] }[] }>('/api/notes/tree')
    setPages(tree.notebooks.flatMap((nb) => nb.pages))
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load reminders.'))
  }, [])

  useEffect(() => {
    const item = Number(params.get('item') || 0)
    if (params.get('attach') === 'page' && item) setPageId(item)
    if (params.get('attach') === 'task' && item) setTaskId(item)
  }, [params])

  const add = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    setError('')
    try {
      await postJson('/api/reminders', {
        name,
        send_at: when,
        repeat_kind: repeat,
        repeat_until: until,
        audience,
        channel,
        sms_to: smsTo,
        items: [
          ...(note.trim() ? [{ item_type: 'text', text: note }] : []),
          ...(taskId ? [{ item_type: 'task', item_id: taskId }] : []),
          ...(pageId ? [{ item_type: 'page', item_id: pageId }] : []),
        ],
        csrf: user.csrf,
      })
      setName('')
      setNote('')
      setOk('Reminder saved.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save that reminder.')
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Reminders</h1>
          <p className="muted">Email, text, or both. Checked boxes are left out of the message.</p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {ok ? <div className="status status--ok">{ok}</div> : null}
      <form className="form form--grid panel" onSubmit={(e) => void add(e)}>
        <label className="field">
          <span className="field__label">Name</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="field">
          <span className="field__label">When</span>
          <input className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
        </label>
        <label className="field">
          <span className="field__label">Repeat</span>
          <select className="input" value={repeat} onChange={(e) => setRepeat(e.target.value)}>
            {REPEATS.map((r) => (
              <option key={r.id} value={r.id}>{r.label}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Until</span>
          <input className="input" type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
        </label>
        <label className="field">
          <span className="field__label">How to send</span>
          <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="email">Email</option>
            <option value="sms">Text</option>
            <option value="both">Email and text</option>
          </select>
        </label>
        <label className="field">
          <span className="field__label">Text number</span>
          <input className="input" value={smsTo} onChange={(e) => setSmsTo(e.target.value)} placeholder="Same as Profile if blank" />
        </label>
        {canFamily ? (
          <label className="field">
            <span className="field__label">Who gets it</span>
            <select className="input" value={audience} onChange={(e) => setAudience(e.target.value)}>
              <option value="personal">Just me</option>
              <option value="family">Whole family</option>
            </select>
          </label>
        ) : null}
        <label className="field">
          <span className="field__label">Attach a to-do</span>
          <select className="input" value={taskId} onChange={(e) => setTaskId(Number(e.target.value))}>
            <option value={0}>None</option>
            {tasks.map((t) => (
              <option key={t.id} value={t.id}>{t.title}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Attach a page</span>
          <select className="input" value={pageId} onChange={(e) => setPageId(Number(e.target.value))}>
            <option value={0}>None</option>
            {pages.map((p) => (
              <option key={p.id} value={p.id}>{p.title}</option>
            ))}
          </select>
        </label>
        <label className="field span-2">
          <span className="field__label">Note to include</span>
          <input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional extra line" />
        </label>
        <div className="span-2">
          <button type="submit" className="btn btn--primary">Save reminder</button>
          <button type="button" className="btn" onClick={() => user && void postJson<{ email: boolean; sms: boolean }>('/api/reminders/ping', { csrf: user.csrf }).then((r) => setOk(`Test sent. Email ${r.email ? 'ok' : 'failed'}, text ${r.sms ? 'ok' : 'failed'}.`))}>
            Send a test now
          </button>
        </div>
      </form>
      <ul className="task-list">
        {rows.map((row) => (
          <li key={row.id} className="task-row">
            <div>
              <strong className="wrap-any">{row.name}</strong>
              <div className="muted">{row.send_at.replace('T', ' ')} · {row.repeat} · {row.audience === 'family' ? 'Family' : 'Just you'}</div>
            </div>
            {user ? (
              <div className="row-actions">
                <button type="button" className="btn btn--small" onClick={() => void postJson(`/api/reminders/${row.id}/send-now`, { csrf: user.csrf }).then(() => setOk('Sent now.'))}>
                  Send now
                </button>
                <button type="button" className="linkish" onClick={() => setDrop(row)}>Cancel</button>
              </div>
            ) : null}
          </li>
        ))}
      </ul>
      {drop && user ? (
        <Confirm
          title="Turn this reminder off?"
          message={drop.name}
          confirmLabel="Turn off"
          onCancel={() => setDrop(null)}
          onConfirm={() => {
            void postJson(`/api/reminders/${drop.id}/cancel`, { csrf: user.csrf }).then(() => {
              setDrop(null)
              void load()
            })
          }}
        />
      ) : null}
    </>
  )
}
