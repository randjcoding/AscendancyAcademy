import { useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import type { Book } from '../types'
import { Confirm } from '../ui/Confirm'
import { Modal } from '../ui/Modal'

type BooksData = {
  books: Book[]
  courses: { id: number; title: string }[]
}

export function Books() {
  const { user, me, setView } = useAuth()
  const [data, setData] = useState<BooksData | null>(null)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Book | null>(null)
  const [drop, setDrop] = useState<Book | null>(null)
  const [error, setError] = useState('')
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [kind, setKind] = useState('other')
  const [lookup, setLookup] = useState('')
  const [courseIds, setCourseIds] = useState<number[]>([])
  const view = user?.list_view || 'cards'

  const load = async () => {
    setData(await api<BooksData>('/api/books'))
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load books.'))
  }, [])

  const startAdd = () => {
    setEditing(null)
    setTitle('')
    setAuthor('')
    setKind('other')
    setLookup('')
    setCourseIds([])
    setOpen(true)
  }

  const startEdit = (book: Book) => {
    setEditing(book)
    setTitle(book.title)
    setAuthor(book.author)
    setKind(book.kind)
    setLookup(book.isbn || book.upc)
    setCourseIds(book.course_ids)
    setOpen(true)
  }

  const save = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    const body = { title, author, kind, lookup, isbn: lookup, course_ids: courseIds, csrf: user.csrf }
    try {
      if (editing) await postJson(`/api/books/${editing.id}`, body)
      else await postJson('/api/books', body)
      setOpen(false)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save that book.')
    }
  }

  if (!data) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Books</h1>
          <p className="muted">The school shelf. Attach a book to one or more classes.</p>
        </div>
        <div className="page-head__actions">
          <div className="view-toggle">
            <button type="button" className={`btn btn--small ${view === 'cards' ? 'btn--primary' : ''}`} onClick={() => void setView('cards')}>Cards</button>
            <button type="button" className={`btn btn--small ${view === 'table' ? 'btn--primary' : ''}`} onClick={() => void setView('table')}>Table</button>
          </div>
          <button type="button" className="btn btn--primary" onClick={startAdd}>Add book</button>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {view === 'table' ? (
        <div className="table-wrap">
          <table className="sheet">
            <thead>
              <tr><th>Title</th><th>Kind</th><th>Classes</th><th></th></tr>
            </thead>
            <tbody>
              {data.books.map((b) => (
                <tr key={b.id}>
                  <td className="wrap-text"><strong>{b.title}</strong><div className="muted">{b.author}</div></td>
                  <td>{b.kind_label}</td>
                  <td className="wrap-text">{b.courses.join(', ') || '—'}</td>
                  <td><button type="button" className="linkish" onClick={() => startEdit(b)}>Edit</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card-grid">
          {data.books.map((b) => (
            <article key={b.id} className="item-card">
              <h3 className="wrap-any">{b.title}</h3>
              <p className="muted">{b.kind_label}{b.author ? ` · ${b.author}` : ''}</p>
              <p className="wrap-any muted">{b.courses.join(', ') || 'Not in a class yet'}</p>
              <button type="button" className="btn" onClick={() => startEdit(b)}>Edit</button>
            </article>
          ))}
        </div>
      )}

      {open ? (
        <Modal title={editing ? 'Edit book' : 'Add book'} onClose={() => setOpen(false)}>
          <form className="form" onSubmit={(e) => void save(e)}>
            <label className="field">
              <span className="field__label">ISBN or UPC</span>
              <input className="input" value={lookup} onChange={(e) => setLookup(e.target.value)} placeholder="Scan or type a code" />
            </label>
            <label className="field">
              <span className="field__label">Title</span>
              <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label className="field">
              <span className="field__label">Author</span>
              <input className="input" value={author} onChange={(e) => setAuthor(e.target.value)} />
            </label>
            <label className="field">
              <span className="field__label">Kind</span>
              <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
                {(me?.book_kinds || []).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            </label>
            <div className="field">
              <span className="field__label">Classes</span>
              <div className="check-grid">
                {data.courses.map((c) => (
                  <label key={c.id} className="check-field">
                    <input
                      type="checkbox"
                      checked={courseIds.includes(c.id)}
                      onChange={(e) => setCourseIds(e.target.checked ? [...courseIds, c.id] : courseIds.filter((id) => id !== c.id))}
                    />
                    <span className="wrap-any">{c.title}</span>
                  </label>
                ))}
              </div>
            </div>
            <button type="submit" className="btn btn--primary">{editing ? 'Save book' : 'Add book'}</button>
            {editing ? (
              <button type="button" className="linkish" onClick={() => { setDrop(editing); setOpen(false) }}>
                Remove this book
              </button>
            ) : null}
          </form>
        </Modal>
      ) : null}

      {drop && user ? (
        <Confirm
          title="Remove this book?"
          message={`${drop.title} will leave the school shelf.`}
          confirmLabel="Remove"
          onCancel={() => setDrop(null)}
          onConfirm={() => {
            void postJson(`/api/books/${drop.id}/delete`, { csrf: user.csrf }).then(() => {
              setDrop(null)
              void load()
            })
          }}
        />
      ) : null}
    </>
  )
}
