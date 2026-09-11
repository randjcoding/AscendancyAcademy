import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Modal } from '../ui/Modal'

type CalEvent = {
  id: string
  title: string
  start: string
  color?: string
}

export function CalendarPage() {
  const { user } = useAuth()
  const [events, setEvents] = useState<CalEvent[]>([])
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [when, setWhen] = useState(new Date().toISOString().slice(0, 10))

  const load = async () => {
    const start = new Date()
    start.setDate(1)
    const end = new Date(start)
    end.setMonth(end.getMonth() + 2)
    const rows = await api<CalEvent[]>(`/api/calendar/events?start=${start.toISOString()}&end=${end.toISOString()}`)
    setEvents(rows)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load the calendar.'))
  }, [])

  const add = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    try {
      await postJson('/api/calendar/events', { title, starts_at: when, csrf: user.csrf })
      setTitle('')
      setOpen(false)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add that day.')
    }
  }

  const grouped = events.reduce<Record<string, CalEvent[]>>((acc, ev) => {
    const key = ev.start.slice(0, 10)
    acc[key] = acc[key] || []
    acc[key].push(ev)
    return acc
  }, {})

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Calendar</h1>
          <p className="muted">Due dates, tasks, and family days.</p>
        </div>
        {user?.is_teacher ? (
          <button type="button" className="btn btn--primary" onClick={() => setOpen(true)}>
            Add a day
          </button>
        ) : null}
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <section className="panel cal-month">
        {Object.keys(grouped).sort().map((day) => (
          <div key={day}>
            <p className="eyebrow">{new Date(day + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</p>
            <ul className="plain-list">
              {grouped[day].map((ev) => (
                <li key={ev.id}>
                  <span className="event-dot" style={{ '--event': ev.color || 'var(--brand)' } as CSSProperties} />
                  <span className="wrap-any">{ev.title}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {!events.length ? <p className="muted">Nothing on the calendar yet.</p> : null}
      </section>
      {open ? (
        <Modal title="Add a day" onClose={() => setOpen(false)}>
          <form className="form" onSubmit={(e) => void add(e)}>
            <label className="field">
              <span className="field__label">Name</span>
              <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </label>
            <label className="field">
              <span className="field__label">Date</span>
              <input className="input" type="date" value={when} onChange={(e) => setWhen(e.target.value)} />
            </label>
            <button type="submit" className="btn btn--primary">Save</button>
          </form>
        </Modal>
      ) : null}
    </>
  )
}
