import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Confirm } from '../ui/Confirm'

type Task = {
  id: number
  title: string
  notes: string
  completed: boolean
  due: string
  scope: string
  course_id: number | null
  inbox: boolean
  can_complete: boolean
  can_edit: boolean
}

type Course = { id: number; title: string }

const FILTERS = [
  { id: '', label: 'All I can see' },
  { id: 'mine', label: 'Mine' },
  { id: 'school', label: 'School' },
  { id: 'class', label: 'This class' },
  { id: 'today', label: 'Today' },
  { id: 'inbox', label: 'Inbox' },
]

export function Tasks() {
  const { user } = useAuth()
  const [tasks, setTasks] = useState<Task[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [filter, setFilter] = useState('')
  const [courseId, setCourseId] = useState(0)
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [scope, setScope] = useState('personal')
  const [error, setError] = useState('')
  const [drop, setDrop] = useState<Task | null>(null)

  const load = async () => {
    const qs = new URLSearchParams()
    if (filter) qs.set('filter', filter)
    if (filter === 'class' && courseId) qs.set('course_id', String(courseId))
    const data = await api<{ tasks: Task[] }>(`/api/tasks${qs.toString() ? `?${qs}` : ''}`)
    setTasks(data.tasks)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load to-dos.'))
  }, [filter, courseId])

  useEffect(() => {
    api<{ courses?: Course[] }>('/api/desk')
      .then((data) => setCourses(data.courses || []))
      .catch(() => {
        api<{ courses?: Course[] }>('/api/student')
          .then((data) => setCourses(data.courses || []))
          .catch(() => setCourses([]))
      })
  }, [])

  const add = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    try {
      await postJson('/api/tasks', {
        title,
        due: due,
        due_date: /^\d{4}-\d{2}-\d{2}$/.test(due) ? due : '',
        scope: user.is_teacher ? scope : 'personal',
        course_id: scope === 'class' ? courseId : 0,
        show_on_calendar: true,
        csrf: user.csrf,
      })
      setTitle('')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add that.')
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>To-do</h1>
          <p className="muted">Yours, the school’s, or a class. Due can be “today” or “fri 3pm”.</p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <div className="weight-toggle">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`btn btn--small ${filter === item.id ? 'btn--primary' : ''}`}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {filter === 'class' && courses.length ? (
        <label className="field">
          <span className="field__label">Class</span>
          <select className="input" value={courseId} onChange={(e) => setCourseId(Number(e.target.value))}>
            <option value={0}>Any class</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.title}</option>
            ))}
          </select>
        </label>
      ) : null}
      {user ? (
        <form className="form form--grid panel" onSubmit={(e) => void add(e)}>
          <label className="field">
            <span className="field__label">New to-do</span>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </label>
          <label className="field">
            <span className="field__label">Due</span>
            <input className="input" value={due} onChange={(e) => setDue(e.target.value)} placeholder="today or 2026-09-14" />
          </label>
          {user.is_teacher ? (
            <label className="field">
              <span className="field__label">Whose</span>
              <select className="input" value={scope} onChange={(e) => setScope(e.target.value)}>
                <option value="personal">Mine</option>
                <option value="school">School</option>
                <option value="class">This class</option>
              </select>
            </label>
          ) : null}
          {user.is_teacher && scope === 'class' ? (
            <label className="field">
              <span className="field__label">Class</span>
              <select className="input" value={courseId} onChange={(e) => setCourseId(Number(e.target.value))}>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>{c.title}</option>
                ))}
              </select>
            </label>
          ) : null}
          <div className="field">
            <button type="submit" className="btn btn--primary">Add</button>
          </div>
        </form>
      ) : null}
      <ul className="task-list">
        {tasks.map((t) => (
          <li key={t.id} className={`task-row ${t.completed ? 'is-done' : ''}`}>
            <div>
              <strong className="wrap-any">{t.title}</strong>
              <div className="muted">{[t.due, t.scope === 'school' ? 'School' : t.scope === 'class' ? 'Class' : 'Mine'].filter(Boolean).join(' · ')}</div>
            </div>
            <div className="row-actions">
              {t.can_complete && user ? (
                <button type="button" className="btn btn--small" onClick={() => void postJson(`/api/tasks/${t.id}/toggle`, { csrf: user.csrf }).then(() => load())}>
                  {t.completed ? 'Not done' : 'Done'}
                </button>
              ) : null}
              {t.can_edit && user ? (
                <button type="button" className="linkish" onClick={() => setDrop(t)}>Remove</button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {drop && user ? (
        <Confirm
          title="Remove this to-do?"
          message={drop.title}
          confirmLabel="Remove"
          onCancel={() => setDrop(null)}
          onConfirm={() => {
            void postJson(`/api/tasks/${drop.id}/delete`, { csrf: user.csrf }).then(() => {
              setDrop(null)
              void load()
            })
          }}
        />
      ) : null}
    </>
  )
}
