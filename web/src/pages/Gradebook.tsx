import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import type { Book, Course } from '../types'

type Assignment = {
  id: number
  title: string
  pages: string
  page_label: string
  has_work: boolean
  due: string
  category: string
  points_possible: number
  book: string
  grade: { points: number; notes: string } | null
}

type Detail = {
  course: Course
  student: { id: number; name: string } | null
  enrollment_id: number | null
  result: { percent: number | null; letter: string | null; categories: { name: string; weight: number; percent: number | null }[] } | null
  assignments: Assignment[]
  catalog_books: Book[]
}

export function Gradebook() {
  const { courseId } = useParams()
  const { user } = useAuth()
  const [data, setData] = useState<Detail | null>(null)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [bookId, setBookId] = useState(0)
  const [pages, setPages] = useState('')
  const [due, setDue] = useState(new Date().toISOString().slice(0, 10))
  const [linkId, setLinkId] = useState(0)

  const load = async () => {
    const row = await api<Detail>(`/api/courses/${courseId}`)
    setData(row)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not open this class.'))
  }, [courseId])

  const saveScore = async (assignmentId: number, points: string) => {
    if (!user || !data?.enrollment_id) return
    try {
      await postJson('/api/grades', {
        assignment_id: assignmentId,
        enrollment_id: data.enrollment_id,
        points_earned: points,
        csrf: user.csrf,
      })
      setOk('Score saved.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save that score.')
    }
  }

  const addPages = async (e: FormEvent) => {
    e.preventDefault()
    if (!user || !courseId) return
    try {
      await postJson('/api/pages', {
        course_id: Number(courseId),
        book_id: bookId,
        pages,
        has_work: true,
        due_date: due,
        show_on_calendar: true,
        csrf: user.csrf,
      })
      setPages('')
      setOk('Pages added.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not add pages.')
    }
  }

  if (!data) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <p className="eyebrow">
            <Link to="/courses">Classes</Link>
          </p>
          <h1 className="wrap-any">{data.course.title}</h1>
          {data.student ? <p className="muted">{data.student.name}</p> : null}
        </div>
        <p className="grade-big">
          {data.result?.letter || '—'} {data.result?.percent != null ? <span>{data.result.percent}%</span> : null}
        </p>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {ok ? <div className="status status--ok">{ok}</div> : null}

      <section className="panel">
        <h2>Add pages</h2>
        <form className="form form--grid" onSubmit={(e) => void addPages(e)}>
          <label className="field">
            <span className="field__label">Book</span>
            <select className="input" value={bookId} onChange={(e) => setBookId(Number(e.target.value))}>
              <option value={0}>No book yet</option>
              {data.course.books.map((b) => (
                <option key={b.id} value={b.id}>{b.title}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Pages</span>
            <input className="input" value={pages} onChange={(e) => setPages(e.target.value)} placeholder="12-15" />
          </label>
          <label className="field">
            <span className="field__label">Due</span>
            <input className="input" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </label>
          <div className="field">
            <button type="submit" className="btn btn--primary">Add pages</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Use a school book</h2>
        <form
          className="form"
          onSubmit={(e) => {
            e.preventDefault()
            if (!user || !linkId) return
            void postJson(`/api/courses/${courseId}/books/link`, { book_id: linkId, csrf: user.csrf }).then(() => load())
          }}
        >
          <select className="input" value={linkId} onChange={(e) => setLinkId(Number(e.target.value))}>
            <option value={0}>Pick a book</option>
            {data.catalog_books.map((b) => (
              <option key={b.id} value={b.id}>{b.title}</option>
            ))}
          </select>
          <button type="submit" className="btn">Add to this class</button>
        </form>
      </section>

      <div className="table-wrap">
        <table className="sheet">
          <thead>
            <tr>
              <th>Work</th>
              <th>Due</th>
              <th>Score</th>
            </tr>
          </thead>
          <tbody>
            {data.assignments.map((a) => (
              <tr key={a.id}>
                <td className="wrap-text">
                  <strong>{a.title}</strong>
                  <div className="muted">{a.page_label || a.category}</div>
                </td>
                <td>{a.due || '—'}</td>
                <td>
                  <form
                    className="score-form"
                    onSubmit={(e) => {
                      e.preventDefault()
                      const input = (e.currentTarget.elements.namedItem('points') as HTMLInputElement)
                      void saveScore(a.id, input.value)
                    }}
                  >
                    <input className="input input--score" name="points" defaultValue={a.grade?.points ?? ''} inputMode="decimal" />
                    <span className="muted">/ {a.points_possible}</span>
                    <button type="submit" className="btn btn--small">Save</button>
                  </form>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
