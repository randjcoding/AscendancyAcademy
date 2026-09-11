import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Confirm } from '../ui/Confirm'

type Task = { id: number; title: string; notes: string; completed: boolean; due: string }

export function Tasks() {
  const { user } = useAuth()
  const [tasks, setTasks] = useState<Task[]>([])
  const [canEdit, setCanEdit] = useState(false)
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [error, setError] = useState('')
  const [drop, setDrop] = useState<Task | null>(null)

  const load = async () => {
    const data = await api<{ can_edit: boolean; tasks: Task[] }>('/api/tasks')
    setTasks(data.tasks)
    setCanEdit(data.can_edit)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load to-dos.'))
  }, [])

  const add = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    try {
      await postJson('/api/tasks', { title, due_date: due, show_on_calendar: true, csrf: user.csrf })
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
          <p className="muted">Small jobs that are not a class assignment.</p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {canEdit ? (
        <form className="form form--grid panel" onSubmit={(e) => void add(e)}>
          <label className="field">
            <span className="field__label">New to-do</span>
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </label>
          <label className="field">
            <span className="field__label">Due</span>
            <input className="input" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </label>
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
              {t.due ? <div className="muted">{t.due}</div> : null}
            </div>
            {canEdit && user ? (
              <div className="row-actions">
                <button type="button" className="btn btn--small" onClick={() => void postJson(`/api/tasks/${t.id}/toggle`, { csrf: user.csrf }).then(() => load())}>
                  {t.completed ? 'Not done' : 'Done'}
                </button>
                <button type="button" className="linkish" onClick={() => setDrop(t)}>Remove</button>
              </div>
            ) : null}
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
