import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Confirm } from '../ui/Confirm'
import { Modal } from '../ui/Modal'
import { NoteEditor } from '../ui/NoteEditor'
import { SortablePages } from '../ui/SortablePages'

type TreePage = {
  id: number
  notebook_id: number
  section_id: number | null
  parent_id: number | null
  title: string
  sort_order: number
}

type Notebook = {
  id: number
  name: string
  scope: string
  course_id: number | null
  can_write: boolean
  sections: { id: number; name: string }[]
  pages: TreePage[]
}

type PageDetail = {
  page: TreePage & { body_html: string; body_json: string; revision: number; scope: string; course_id: number | null }
  can_write: boolean
  tasks: { id: number; title: string; completed: boolean; due: string }[]
}

export function Notes() {
  const { pageId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [trash, setTrash] = useState(false)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<{ id: number; title: string; snippet: string }[]>([])
  const [detail, setDetail] = useState<PageDetail | null>(null)
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [drop, setDrop] = useState<TreePage | null>(null)
  const [history, setHistory] = useState<{ id: number; title: string; created_at: string }[] | null>(null)
  const [bringOpen, setBringOpen] = useState(false)
  const [openTasks, setOpenTasks] = useState<{ id: number; title: string }[]>([])
  const [makeTitle, setMakeTitle] = useState('')
  const [makeDue, setMakeDue] = useState('')

  const currentId = Number(pageId || 0)

  const loadTree = async (showTrash = trash) => {
    const data = await api<{ notebooks: Notebook[] }>(`/api/notes/tree${showTrash ? '?trash=1' : ''}`)
    setNotebooks(data.notebooks)
  }

  const loadPage = async (id: number) => {
    const data = await api<PageDetail>(`/api/notes/pages/${id}`)
    setDetail(data)
    setTitle(data.page.title)
  }

  useEffect(() => {
    loadTree().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load notes.'))
  }, [trash])

  useEffect(() => {
    if (!currentId) {
      setDetail(null)
      return
    }
    loadPage(currentId).catch((err) => setError(err instanceof ApiError ? err.message : 'Could not open that page.'))
  }, [currentId])

  useEffect(() => {
    if (query.trim().length < 2) {
      setHits([])
      return
    }
    const t = window.setTimeout(() => {
      api<{ pages: { id: number; title: string; snippet: string }[] }>(`/api/notes/search?q=${encodeURIComponent(query)}`)
        .then((data) => setHits(data.pages))
        .catch(() => setHits([]))
    }, 250)
    return () => window.clearTimeout(t)
  }, [query])

  const addPage = async (notebook: Notebook, parentId = 0) => {
    if (!user) return
    const sectionId = notebook.sections[0]?.id || 0
    const created = await postJson<{ page: { id: number } }>('/api/notes/pages', {
      notebook_id: notebook.id,
      section_id: sectionId,
      parent_id: parentId,
      title: 'Untitled',
      csrf: user.csrf,
    })
    await loadTree()
    navigate(`/notes/${created.page.id}`)
  }

  const childrenOf = (pages: TreePage[], parentId: number | null) =>
    pages.filter((p) => (p.parent_id || null) === parentId).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)

  const renderPages = (notebook: Notebook, parentId: number | null, depth: number) =>
    childrenOf(notebook.pages, parentId).map((page) => (
      <div key={page.id} className="note-tree-node" style={{ paddingLeft: `${depth * 0.7}rem` }}>
        <Link to={`/notes/${page.id}`} className={`tree-item ${currentId === page.id ? 'is-on' : ''}`}>
          <span className="wrap-any">{page.title || 'Untitled'}</span>
        </Link>
        {notebook.can_write && depth < 4 ? (
          <button type="button" className="linkish" onClick={() => void addPage(notebook, page.id)}>
            Subpage
          </button>
        ) : null}
        {renderPages(notebook, page.id, depth + 1)}
      </div>
    ))

  const visibleBooks = useMemo(() => notebooks, [notebooks])

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Notes</h1>
          <p className="muted">Personal pages stay yours. School and class pages are for the family.</p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <div className="notes-desk">
        <aside className="panel notes-nav">
          <label className="field">
            <span className="field__label">Find a page</span>
            <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Title or words" />
          </label>
          {hits.length ? (
            <ul className="plain-list">
              {hits.map((hit) => (
                <li key={hit.id}>
                  <Link to={`/notes/${hit.id}`} className="wrap-any">{hit.title}</Link>
                  <span className="muted">{hit.snippet}</span>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="row-actions">
            <button type="button" className="btn btn--small" onClick={() => setTrash((v) => !v)}>
              {trash ? 'Open pages' : 'Trash'}
            </button>
          </div>
          {visibleBooks.map((nb) => (
            <section key={nb.id} className="notes-book">
              <div className="notes-book__head">
                <h2 className="wrap-any">{nb.name}</h2>
                {nb.can_write && !trash ? (
                  <button type="button" className="btn btn--small" onClick={() => void addPage(nb)}>
                    Add page
                  </button>
                ) : null}
              </div>
              <p className="muted">{nb.scope === 'personal' ? 'Only you' : nb.scope === 'school' ? 'Whole family' : 'This class'}</p>
              {nb.can_write && !trash ? (
                <SortablePages pages={nb.pages} currentId={currentId} onMoved={() => void loadTree()} />
              ) : (
                renderPages(nb, null, 0)
              )}
              {nb.can_write && !trash
                ? childrenOf(nb.pages, null).flatMap((page) => renderPages(nb, page.id, 1))
                : null}
            </section>
          ))}
        </aside>
        <section className="panel notes-page">
          {!detail ? (
            <p className="muted">Pick a page, or add one in your notebook.</p>
          ) : (
            <>
              <NoteEditor
                key={detail.page.id}
                pageId={detail.page.id}
                title={title}
                bodyHtml={detail.page.body_html}
                revision={detail.page.revision}
                canWrite={detail.can_write && !trash}
                onTitle={setTitle}
                onSaved={(rev, nextTitle) => {
                  setTitle(nextTitle)
                  setDetail((cur) => (cur ? { ...cur, page: { ...cur.page, revision: rev, title: nextTitle } } : cur))
                  void loadTree()
                }}
                onMakeTask={(text) => setMakeTitle(text)}
              />
              <div className="row-actions">
                <button
                  type="button"
                  className="btn btn--small"
                  onClick={() => {
                    api<{ tasks: { id: number; title: string }[] }>('/api/tasks?filter=mine')
                      .then((data) => {
                        setOpenTasks(data.tasks)
                        setBringOpen(true)
                      })
                      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load to-dos.'))
                  }}
                >
                  Bring in tasks
                </button>
                <button
                  type="button"
                  className="btn btn--small"
                  onClick={() => {
                    api<{ history: { id: number; title: string; created_at: string }[] }>(`/api/notes/pages/${detail.page.id}/history`)
                      .then((data) => setHistory(data.history))
                      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load history.'))
                  }}
                >
                  History
                </button>
                {detail.can_write ? (
                  trash ? (
                    <button
                      type="button"
                      className="btn btn--small"
                      onClick={() => user && void postJson(`/api/notes/pages/${detail.page.id}/restore`, { csrf: user.csrf }).then(() => { void loadTree(); navigate('/notes') })}
                    >
                      Put back
                    </button>
                  ) : (
                    <button type="button" className="linkish" onClick={() => setDrop(detail.page)}>
                      Move to trash
                    </button>
                  )
                ) : null}
              </div>
              {detail.tasks.length ? (
                <ul className="plain-list">
                  {detail.tasks.map((t) => (
                    <li key={t.id}>
                      <Link to="/tasks">{t.completed ? 'Done · ' : ''}{t.title}</Link>
                    </li>
                  ))}
                </ul>
              ) : null}
            </>
          )}
        </section>
      </div>
      {drop && user ? (
        <Confirm
          title="Move this page to trash?"
          message={drop.title}
          confirmLabel="Trash"
          onCancel={() => setDrop(null)}
          onConfirm={() => {
            void postJson(`/api/notes/pages/${drop.id}/delete`, { csrf: user.csrf }).then(() => {
              setDrop(null)
              void loadTree()
              navigate('/notes')
            })
          }}
        />
      ) : null}
      {makeTitle && user && detail ? (
        <Modal
          title="Make a to-do from this note"
          onClose={() => setMakeTitle('')}
          actions={
            <>
              <button type="button" className="btn" onClick={() => setMakeTitle('')}>Cancel</button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => {
                  void postJson(`/api/notes/pages/${detail.page.id}/make-task`, {
                    title: makeTitle,
                    due: makeDue,
                    scope: detail.page.scope,
                    course_id: detail.page.course_id || 0,
                    csrf: user.csrf,
                  }).then(() => {
                    setMakeTitle('')
                    setMakeDue('')
                    void loadPage(detail.page.id)
                  })
                }}
              >
                Make task
              </button>
            </>
          }
        >
          <label className="field">
            <span className="field__label">To-do</span>
            <input className="input" value={makeTitle} onChange={(e) => setMakeTitle(e.target.value)} />
          </label>
          <label className="field">
            <span className="field__label">Due</span>
            <input className="input" value={makeDue} onChange={(e) => setMakeDue(e.target.value)} placeholder="today, tomorrow, fri 3pm" />
          </label>
        </Modal>
      ) : null}
      {bringOpen && user && detail ? (
        <Modal
          title="Bring in a to-do"
          onClose={() => setBringOpen(false)}
          actions={<button type="button" className="btn" onClick={() => setBringOpen(false)}>Close</button>}
        >
          {openTasks.length ? (
            <ul className="plain-list">
              {openTasks.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    className="btn btn--small"
                    onClick={() => {
                      void postJson(`/api/notes/pages/${detail.page.id}/bring-in-task`, { task_id: t.id, csrf: user.csrf }).then(() => {
                        setBringOpen(false)
                        void loadPage(detail.page.id)
                      })
                    }}
                  >
                    {t.title}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No personal to-dos yet.</p>
          )}
        </Modal>
      ) : null}
      {history && user && detail ? (
        <Modal
          title="Earlier versions"
          onClose={() => setHistory(null)}
          actions={<button type="button" className="btn" onClick={() => setHistory(null)}>Close</button>}
        >
          {history.length ? (
            <ul className="plain-list">
              {history.map((h) => (
                <li key={h.id}>
                  <span className="wrap-any">{h.title}</span>
                  <span className="muted">{h.created_at}</span>
                  {detail.can_write ? (
                    <button
                      type="button"
                      className="btn btn--small"
                      onClick={() => {
                        void postJson<{ page?: { body_html: string; revision: number; title: string } }>(`/api/notes/pages/${detail.page.id}/history/${h.id}/restore`, { csrf: user.csrf }).then((row) => {
                          setHistory(null)
                          if (row.page) {
                            setDetail((cur) => (cur ? { ...cur, page: { ...cur.page, ...row.page } } : cur))
                            setTitle(row.page.title)
                          }
                        })
                      }}
                    >
                      Put this back
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No older copies yet.</p>
          )}
        </Modal>
      ) : null}
    </>
  )
}
