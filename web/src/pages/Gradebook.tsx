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
  const [tab, setTab] = useState<'about' | 'grades'>('about')
  const [info, setInfo] = useState({
    description: '', schedule: '', location: '', grade_level: '', credit_hours: '',
    goals: '', materials: '', teacher_notes: '', student_brief: '',
  })

  const load = async () => {
    const row = await api<Detail>(`/api/courses/${courseId}`)
    setData(row)
    setInfo({
      description: row.course.description || '',
      schedule: row.course.schedule || '',
      location: row.course.location || '',
      grade_level: row.course.grade_level || '',
      credit_hours: row.course.credit_hours || '',
      goals: row.course.goals || '',
      materials: row.course.materials || '',
      teacher_notes: row.course.teacher_notes || '',
      student_brief: row.course.student_brief || '',
    })
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
      <div className="weight-toggle">
        <button type="button" className={`btn btn--small ${tab === 'about' ? 'btn--primary' : ''}`} onClick={() => setTab('about')}>About this class</button>
        <button type="button" className={`btn btn--small ${tab === 'grades' ? 'btn--primary' : ''}`} onClick={() => setTab('grades')}>Gradebook</button>
      </div>
      {tab === 'about' ? (
        <section className="panel">
          <h2>Class information</h2>
          <p className="muted">What you and Gregory need to know besides scores.</p>
          <form className="form form--grid" onSubmit={(e) => {
            e.preventDefault()
            if (!user) return
            void postJson(`/api/courses/${courseId}/info`, { ...info, csrf: user.csrf }).then(() => {
              setOk('Class information saved.')
              void load()
            }).catch((err) => setError(err instanceof ApiError ? err.message : 'Could not save that.'))
          }}>
            <label className="field span-2"><span className="field__label">What this class is</span>
              <textarea className="input" rows={3} value={info.description} onChange={(e) => setInfo({ ...info, description: e.target.value })} /></label>
            <label className="field"><span className="field__label">When we meet</span>
              <input className="input" value={info.schedule} onChange={(e) => setInfo({ ...info, schedule: e.target.value })} placeholder="Mon / Wed mornings" /></label>
            <label className="field"><span className="field__label">Where</span>
              <input className="input" value={info.location} onChange={(e) => setInfo({ ...info, location: e.target.value })} placeholder="Kitchen table" /></label>
            <label className="field"><span className="field__label">Grade level</span>
              <input className="input" value={info.grade_level} onChange={(e) => setInfo({ ...info, grade_level: e.target.value })} /></label>
            <label className="field"><span className="field__label">Credit</span>
              <input className="input" value={info.credit_hours} onChange={(e) => setInfo({ ...info, credit_hours: e.target.value })} placeholder="1" /></label>
            <label className="field span-2"><span className="field__label">Goals</span>
              <textarea className="input" rows={3} value={info.goals} onChange={(e) => setInfo({ ...info, goals: e.target.value })} /></label>
            <label className="field span-2"><span className="field__label">Materials</span>
              <textarea className="input" rows={3} value={info.materials} onChange={(e) => setInfo({ ...info, materials: e.target.value })} /></label>
            <label className="field span-2"><span className="field__label">Notes for Gregory</span>
              <textarea className="input" rows={3} value={info.student_brief} onChange={(e) => setInfo({ ...info, student_brief: e.target.value })} /></label>
            <label className="field span-2"><span className="field__label">Private teacher notes</span>
              <textarea className="input" rows={3} value={info.teacher_notes} onChange={(e) => setInfo({ ...info, teacher_notes: e.target.value })} /></label>
            <div className="span-2"><button type="submit" className="btn btn--primary">Save class info</button></div>
          </form>
        </section>
      ) : null}
      {tab === 'grades' ? (
      <>
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
      ) : null}
    </>
  )
}
