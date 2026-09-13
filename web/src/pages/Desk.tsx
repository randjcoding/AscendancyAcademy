import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import type { Book, Course, DayCell, Totals } from '../types'
import { Board } from '../ui/Board'
import { AttendanceCell } from './Attendance'

type DeskData = {
  today: string
  student: { id: number; name: string } | null
  today_status: string
  today_locked: boolean
  totals: Totals | null
  gemma_available: boolean
  week: DayCell[]
  courses: Course[]
  waiting: { course: string; title: string; pages: string; due: string }[]
  upcoming: { course: string; title: string; due: string }[]
  keys: { id: number; name: string; provider: string }[]
}

export function Desk() {
  const { user } = useAuth()
  const [data, setData] = useState<DeskData | null>(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [courseId, setCourseId] = useState(0)
  const [bookId, setBookId] = useState(0)
  const [pages, setPages] = useState('')
  const [bulk, setBulk] = useState('')
  const [score, setScore] = useState('')
  const [due, setDue] = useState('')
  const [hasWork, setHasWork] = useState(true)
  const [onCal, setOnCal] = useState(true)
  const [provider, setProvider] = useState('')
  const [keyId, setKeyId] = useState(0)
  const [photos, setPhotos] = useState<FileList | null>(null)
  const [estimate, setEstimate] = useState('Pick a model and photos to see the cost.')

  const load = async () => {
    const row = await api<DeskData>('/api/desk')
    setData(row)
    if (!courseId && row.courses[0]) setCourseId(row.courses[0].id)
    if (!due) setDue(row.today)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load the desk.'))
  }, [])

  const books = useMemo(() => {
    const course = data?.courses.find((c) => c.id === courseId)
    return course?.books || []
  }, [data, courseId])

  const markToday = async (status: string) => {
    if (!data?.student || !user) return
    try {
      await postJson('/api/attendance/day', { student_id: data.student.id, on_date: data.today, status, csrf: user.csrf })
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not mark today.')
    }
  }

  const assign = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    setError('')
    try {
      const result = await postJson<{ count: number }>('/api/pages', {
        course_id: courseId,
        book_id: bookId,
        pages,
        bulk_pages: bulk,
        has_work: hasWork,
        due_date: due,
        show_on_calendar: onCal,
        points_earned: score,
        csrf: user.csrf,
      })
      setOk(`Added ${result.count} page set${result.count === 1 ? '' : 's'}.`)
      setPages('')
      setBulk('')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add those pages.')
    }
  }

  const readPhotos = async () => {
    if (!photos?.length) {
      setEstimate('Add at least one photo.')
      return
    }
    const body = new FormData()
    body.set('provider', provider)
    body.set('key_id', String(keyId))
    body.set('book_id', String(bookId))
    Array.from(photos).forEach((f) => body.append('files', f))
    setEstimate('Reading…')
    try {
      const guess = await api<{ pages?: string; error?: string }>('/teacher/read-pages', { method: 'POST', body })
      if (guess.pages) setPages(guess.pages)
      setEstimate(guess.error || 'Check the pages, then add them.')
    } catch (err) {
      setEstimate(err instanceof ApiError ? err.message : 'Could not read those photos.')
    }
  }

  if (!data) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Teacher desk</h1>
          <p className="muted">
            {new Date(data.today + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
            {data.student ? ` · ${data.student.name}` : ''}
          </p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {ok ? <div className="status status--ok">{ok}</div> : null}

      <Board />

      {data.student ? (
        <section className="panel">
          <div className="panel__head">
            <div>
              <p className="eyebrow">Today’s attendance</p>
              <h2 className="wrap-any">{data.student.name}</h2>
              {data.totals ? (
                <p className="muted">
                  {data.totals.present} present · {data.totals.remaining} left toward {data.totals.target}
                </p>
              ) : null}
            </div>
            {data.today_status ? <p className={`pill pill--${data.today_status}`}>Today: {data.today_status}</p> : null}
          </div>
          <div className="attend-actions">
            {(['present', 'absent', 'sick', 'excused', 'off', 'clear'] as const).map((status) => (
              <button
                key={status}
                type="button"
                className={`btn btn--xl ${data.today_status === status ? 'btn--primary' : ''}`}
                onClick={() => void markToday(status)}
              >
                {status === 'off' ? 'Day off' : status[0].toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
          <div className="week-strip" aria-label="This week">
            {data.week.map((day) => (
              <AttendanceCell
                key={day.date}
                day={day}
                studentId={data.student!.id}
                csrf={user?.csrf || ''}
                canEdit
                compact
                onChanged={() => void load()}
              />
            ))}
          </div>
        </section>
      ) : null}

      <section className="panel">
        <p className="eyebrow">Add work</p>
        <h2>Assign pages</h2>
        <p className="muted">
          Pick the class and book, then type pages. One range like <strong>12-15</strong>, or many lines.
        </p>
        <form className="form form--grid" onSubmit={(e) => void assign(e)}>
          <label className="field">
            <span className="field__label">Class</span>
            <select className="input" value={courseId} onChange={(e) => { setCourseId(Number(e.target.value)); setBookId(0) }}>
              {data.courses.map((c) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Book</span>
            <select className="input" value={bookId} onChange={(e) => setBookId(Number(e.target.value))}>
              <option value={0}>No book yet</option>
              {books.map((b: Book) => (
                <option key={b.id} value={b.id}>{b.title}</option>
              ))}
            </select>
          </label>
          <div className="span-2 panel docs-add">
            <p className="field__label">Read from photos</p>
            <label className="field">
              <span className="field__label">Photos</span>
              <input className="input" type="file" accept="image/*" multiple onChange={(e) => setPhotos(e.target.files)} />
            </label>
            <label className="field">
              <span className="field__label">Model</span>
              <select className="input" value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="">Pick one</option>
                <option value="gemma" disabled={!data.gemma_available}>Gemma on the Mac {data.gemma_available ? '' : '— not on'}</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </label>
            <label className="field">
              <span className="field__label">Key</span>
              <select className="input" value={keyId} onChange={(e) => setKeyId(Number(e.target.value))}>
                <option value={0}>None needed for Gemma</option>
                {data.keys.map((k) => (
                  <option key={k.id} value={k.id}>{k.name} ({k.provider})</option>
                ))}
              </select>
            </label>
            <p className="muted">{estimate}</p>
            <button type="button" className="btn" onClick={() => void readPhotos()}>
              Read pages
            </button>
          </div>
          <label className="field">
            <span className="field__label">Pages today</span>
            <input className="input" value={pages} onChange={(e) => setPages(e.target.value)} placeholder="12-15 or 12, 18, 20-22" />
          </label>
          <label className="field">
            <span className="field__label">Score if already marked</span>
            <input className="input" value={score} onChange={(e) => setScore(e.target.value)} inputMode="decimal" />
          </label>
          <label className="field">
            <span className="field__label">Due</span>
            <input className="input" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </label>
          <label className="field span-2">
            <span className="field__label">Or paste many days at once</span>
            <textarea className="input" rows={5} value={bulk} onChange={(e) => setBulk(e.target.value)} placeholder={'12-15 work\n16-18 reading'} />
          </label>
          <label className="field check-field">
            <input type="checkbox" checked={hasWork} onChange={(e) => setHasWork(e.target.checked)} />
            <span>These pages have work to turn in</span>
          </label>
          <label className="field check-field">
            <input type="checkbox" checked={onCal} onChange={(e) => setOnCal(e.target.checked)} />
            <span>Put on the calendar</span>
          </label>
          <div className="span-2">
            <button type="submit" className="btn btn--primary btn--xl">Add pages</button>
          </div>
        </form>
      </section>

      <div className="quick-row">
        <Link className="quick-btn" to="/attendance">Attendance</Link>
        <Link className="quick-btn" to="/courses">Classes</Link>
        <Link className="quick-btn" to="/books">Find a book</Link>
        <Link className="quick-btn" to="/documents">Add files</Link>
      </div>

      <div className="split">
        <section className="panel">
          <h2>Waiting on a score</h2>
          {data.waiting.length ? (
            <ul className="plain-list">
              {data.waiting.map((w) => (
                <li key={`${w.course}-${w.title}`}>
                  <span className="wrap-any">{w.title}</span>
                  <span className="muted">{w.course}{w.pages ? ` · ${w.pages}` : ''}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing waiting.</p>
          )}
        </section>
        <section className="panel">
          <h2>Coming up</h2>
          {data.upcoming.length ? (
            <ul className="plain-list">
              {data.upcoming.map((w) => (
                <li key={`${w.course}-${w.title}-${w.due}`}>
                  <span className="wrap-any">{w.title}</span>
                  <span className="muted">{w.course} · {w.due}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing due soon.</p>
          )}
        </section>
      </div>
    </>
  )
}
