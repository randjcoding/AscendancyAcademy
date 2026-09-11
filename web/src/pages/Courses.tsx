import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import type { Course } from '../types'
import { ColorPicker } from '../ui/ColorPicker'
import { Confirm } from '../ui/Confirm'
import { Modal } from '../ui/Modal'

export function Courses() {
  const { user, setView } = useAuth()
  const [courses, setCourses] = useState<Course[]>([])
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [color, setColor] = useState('#2D6A4F')
  const [equal, setEqual] = useState(true)
  const [weights, setWeights] = useState({ tests: 25, quizzes: 25, assignments: 25, other: 25 })
  const [error, setError] = useState('')
  const [drop, setDrop] = useState<Course | null>(null)
  const view = user?.list_view || 'cards'

  const load = async () => {
    const data = await api<{ courses: Course[] }>('/api/courses')
    setCourses(data.courses)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load classes.'))
  }, [])

  const create = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    setError('')
    try {
      await postJson('/api/courses', {
        title,
        color,
        equal_weights: equal,
        tests_weight: weights.tests,
        quizzes_weight: weights.quizzes,
        assignments_weight: weights.assignments,
        other_weight: weights.other,
        csrf: user.csrf,
      })
      setTitle('')
      setEqual(true)
      setOpen(false)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add that class.')
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Classes</h1>
          <p className="muted">Add a class, then open it to score work.</p>
        </div>
        <div className="page-head__actions">
          <div className="view-toggle">
            <button type="button" className={`btn btn--small ${view === 'cards' ? 'btn--primary' : ''}`} onClick={() => void setView('cards')}>
              Cards
            </button>
            <button type="button" className={`btn btn--small ${view === 'table' ? 'btn--primary' : ''}`} onClick={() => void setView('table')}>
              Table
            </button>
          </div>
          <button type="button" className="btn btn--primary" onClick={() => setOpen(true)}>
            New class
          </button>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {view === 'table' ? (
        <div className="table-wrap">
          <table className="sheet">
            <thead>
              <tr>
                <th>Class</th>
                <th>Grade</th>
                <th>Books</th>
              </tr>
            </thead>
            <tbody>
              {courses.map((c) => (
                <tr key={c.id}>
                  <td className="wrap-text">
                    <Link to={`/courses/${c.id}`}>{c.title}</Link>
                  </td>
                  <td>{c.letter ? `${c.letter} ${c.percent ?? ''}` : '—'}</td>
                  <td>{c.book_count ?? c.books.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card-grid">
          {courses.map((c) => (
            <article key={c.id} className="class-card" style={{ '--course': c.color } as CSSProperties}>
              <h2 className="wrap-any">{c.title}</h2>
              <p className="grade-big">
                {c.letter || '—'} {c.percent != null ? <span>{c.percent}%</span> : null}
              </p>
              <p>
                <Link className="btn btn--primary" to={`/courses/${c.id}`}>
                  Open gradebook
                </Link>
              </p>
              <p>
                <button type="button" className="linkish" onClick={() => setDrop(c)}>
                  Remove class
                </button>
              </p>
            </article>
          ))}
        </div>
      )}

      {open ? (
        <Modal title="New class" onClose={() => setOpen(false)}>
          <form className="form" onSubmit={(e) => void create(e)}>
            <label className="field">
              <span className="field__label">Class name</span>
              <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus />
            </label>
            <div className="field">
              <span className="field__label">Color</span>
              <ColorPicker value={color} onChange={setColor} />
            </div>
            <div className="field">
              <span className="field__label">Grade weights</span>
              <div className="weight-toggle">
                <button type="button" className={`btn ${equal ? 'btn--primary' : ''}`} onClick={() => setEqual(true)}>
                  Same for all
                </button>
                <button type="button" className={`btn ${!equal ? 'btn--primary' : ''}`} onClick={() => setEqual(false)}>
                  Set percents
                </button>
              </div>
              {equal ? (
                <p className="muted">Tests, quizzes, assignments, and other each count 25%.</p>
              ) : (
                <div className="weight-fields">
                  {(['tests', 'quizzes', 'assignments', 'other'] as const).map((key) => (
                    <label key={key} className="field">
                      <span className="field__label">{key[0].toUpperCase() + key.slice(1)}</span>
                      <input
                        className="input"
                        type="number"
                        min={0}
                        max={100}
                        value={weights[key]}
                        onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })}
                      />
                    </label>
                  ))}
                </div>
              )}
            </div>
            <button type="submit" className="btn btn--primary btn--xl">
              Add class
            </button>
          </form>
        </Modal>
      ) : null}

      {drop && user ? (
        <Confirm
          title="Remove this class?"
          message={`${drop.title} and its scores will be gone.`}
          confirmLabel="Remove"
          onCancel={() => setDrop(null)}
          onConfirm={() => {
            void postJson(`/api/courses/${drop.id}/delete`, { csrf: user.csrf }).then(() => {
              setDrop(null)
              void load()
            })
          }}
        />
      ) : null}
    </>
  )
}
