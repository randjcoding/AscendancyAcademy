import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { BoxCanvas, NoteToolbar, type NoteBox } from '../ui/BoxCanvas'
import { Confirm } from '../ui/Confirm'
import { Modal } from '../ui/Modal'

type TreePage = {
  id: number
  notebook_id: number
  section_id: number | null
  parent_id: number | null
  title: string
  kind: string
  sort_order: number
}

type Section = { id: number; name: string; color: string }
type Notebook = {
  id: number
  name: string
  color: string
  scope: string
  course_id: number | null
  can_write: boolean
  sections: Section[]
  pages: TreePage[]
}

type PageDetail = {
  page: TreePage & { body_html: string; revision: number; scope: string; course_id: number | null }
  boxes: NoteBox[]
  can_write: boolean
  tasks: { id: number; title: string; completed: boolean; due: string }[]
}

export function Notes() {
  const { pageId } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [notebooks, setNotebooks] = useState<Notebook[]>([])
  const [notebookId, setNotebookId] = useState(0)
  const [sectionId, setSectionId] = useState(0)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<{ id: number; title: string; snippet: string }[]>([])
  const [detail, setDetail] = useState<PageDetail | null>(null)
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [drop, setDrop] = useState<TreePage | null>(null)
  const [history, setHistory] = useState<{ id: number; title: string; created_at: string }[] | null>(null)
  const [makeTitle, setMakeTitle] = useState('')
  const [makeDue, setMakeDue] = useState('')
  const [bringOpen, setBringOpen] = useState(false)
  const [openTasks, setOpenTasks] = useState<{ id: number; title: string }[]>([])
  const [shareOpen, setShareOpen] = useState(false)
  const [shareScope, setShareScope] = useState('personal')
  const [newBook, setNewBook] = useState('')
  const [conflict, setConflict] = useState(false)
  const [folded, setFolded] = useState<Record<number, boolean>>({})
  const [hideFmt, setHideFmt] = useState(() => {
    try { return localStorage.getItem('aa.notes.hideFmt') === '1' } catch { return false }
  })
  const [bookEdit, setBookEdit] = useState(false)
  const [bookName, setBookName] = useState('')
  const [bookColor, setBookColor] = useState('#d4b44a')
  const [secColor, setSecColor] = useState('#2d6a4f')
  const [courses, setCourses] = useState<{ id: number; title: string }[]>([])
  const [shareCourse, setShareCourse] = useState(0)
  const [hasDraft, setHasDraft] = useState(false)
  const [dropSec, setDropSec] = useState<Section | null>(null)
  const [dropBook, setDropBook] = useState(false)

  const currentId = Number(pageId || 0)
  const notebook = notebooks.find((n) => n.id === notebookId) || notebooks[0]
  const pages = useMemo(
    () => (notebook?.pages || []).filter((p) => !sectionId || p.section_id === sectionId),
    [notebook, sectionId],
  )

  const loadTree = async () => {
    const data = await api<{ notebooks: Notebook[] }>('/api/notes/tree')
    setNotebooks(data.notebooks)
    return data.notebooks
  }

  const loadPage = async (id: number) => {
    const data = await api<PageDetail>(`/api/notes/pages/${id}`)
    setDetail(data)
    setTitle(data.page.title)
    setShareScope(data.page.scope)
    setConflict(false)
  }

  useEffect(() => {
    loadTree()
      .then((books) => {
        if (!notebookId && books[0]) {
          setNotebookId(books[0].id)
          setSectionId(books[0].sections[0]?.id || 0)
        }
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load notes.'))
    if (user?.is_teacher) {
      api<{ courses: { id: number; title: string }[] }>('/api/courses')
        .then((data) => setCourses(data.courses))
        .catch(() => setCourses([]))
    }
  }, [])

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

  useEffect(() => {
    if (!detail) return
    setNotebookId(detail.page.notebook_id)
    if (detail.page.section_id) setSectionId(detail.page.section_id)
    setShareCourse(detail.page.course_id || 0)
    try {
      setHasDraft(Boolean(localStorage.getItem(`aa.note.draft.${detail.page.id}`)))
    } catch {
      setHasDraft(false)
    }
  }, [detail?.page.id])

  const addPage = async (kind = 'note', parentId = 0) => {
    if (!user || !notebook) return
    const created = await postJson<{ page: { id: number } }>('/api/notes/pages', {
      notebook_id: notebook.id,
      section_id: sectionId || notebook.sections[0]?.id || 0,
      parent_id: parentId,
      title: kind === 'list' ? 'List' : 'Untitled',
      kind,
      csrf: user.csrf,
    })
    await loadTree()
    navigate(`/notes/${created.page.id}`)
  }

  const childrenOf = (parentId: number | null) =>
    pages.filter((p) => (p.parent_id || null) === parentId).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)

  const [renameSec, setRenameSec] = useState<Section | null>(null)
  const [renameVal, setRenameVal] = useState('')

  const renderTree = (parentId: number | null, depth: number): ReactNode =>
    childrenOf(parentId).map((page) => {
      const kids = childrenOf(page.id)
      const closed = folded[page.id]
      return (
        <div key={page.id} className="onenote-page" style={{ paddingLeft: `${depth * 0.65}rem` }}>
          <div className="onenote-page__row">
            {kids.length ? (
              <button type="button" className="btn btn--ghost btn--small" onClick={() => setFolded((f) => ({ ...f, [page.id]: !f[page.id] }))}>
                {closed ? '+' : '−'}
              </button>
            ) : <span className="onenote-page__dot" />}
            <button
              type="button"
              className={`tree-item ${currentId === page.id ? 'is-on' : ''}`}
              onClick={() => navigate(`/notes/${page.id}`)}
            >
              <span className="wrap-any">{page.kind === 'list' ? '☑ ' : ''}{page.title || 'Untitled'}</span>
            </button>
          </div>
          {!closed ? renderTree(page.id, depth + 1) : null}
        </div>
      )
    })

  const saveTitle = (value: string) => {
    setTitle(value)
    if (!user || !detail) return
    void postJson<{ revision: number }>(`/api/notes/pages/${detail.page.id}/save`, {
      csrf: user.csrf,
      revision: detail.page.revision,
      title: value,
      body_html: detail.page.body_html,
    }).then((row) => {
      setDetail((cur) => (cur ? { ...cur, page: { ...cur.page, revision: row.revision, title: value } } : cur))
    }).catch((err) => {
      if (err instanceof ApiError && err.status === 409) setConflict(true)
    })
  }

  return (
    <div className="onenote">
      <aside className="onenote__books panel">
        <label className="field">
          <span className="field__label">Find a page</span>
          <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Title or words" />
        </label>
        {hits.map((hit) => (
          <button key={hit.id} type="button" className="tree-item" onClick={() => navigate(`/notes/${hit.id}`)}>
            <span className="wrap-any">{hit.title}</span>
          </button>
        ))}
        {notebooks.map((nb) => (
          <button
            key={nb.id}
            type="button"
            className={`onenote-book ${notebookId === nb.id ? 'is-on' : ''}`}
            onClick={() => {
              setNotebookId(nb.id)
              setSectionId(nb.sections[0]?.id || 0)
            }}
          >
            <span className="onenote-book__dot" style={{ background: nb.color }} />
            <span className="wrap-any">{nb.name}</span>
          </button>
        ))}
        {notebook?.can_write ? (
          <button type="button" className="linkish" onClick={() => {
            setBookName(notebook.name)
            setBookColor(notebook.color || '#d4b44a')
            setBookEdit(true)
          }}>Notebook settings</button>
        ) : null}
        <form
          className="onenote-add"
          onSubmit={(e) => {
            e.preventDefault()
            if (!user || !newBook.trim()) return
            void postJson('/api/notes/notebooks', { name: newBook, scope: 'personal', csrf: user.csrf }).then(() => {
              setNewBook('')
              void loadTree()
            })
          }}
        >
          <input className="input" value={newBook} onChange={(e) => setNewBook(e.target.value)} placeholder="New notebook" />
          <button type="submit" className="btn btn--small">Add</button>
        </form>
      </aside>
      <div className="onenote__main">
        <div className="onenote__tabs">
          {(notebook?.sections || []).map((sec) => (
            <button
              key={sec.id}
              type="button"
              className={`onenote-tab ${sectionId === sec.id ? 'is-on' : ''}`}
              style={{ ['--tab' as string]: sec.color }}
              onClick={() => setSectionId(sec.id)}
              onDoubleClick={() => {
                if (!user || !notebook?.can_write) return
                setRenameSec(sec)
                setRenameVal(sec.name)
                setSecColor(sec.color || '#2d6a4f')
              }}
            >
              {sec.name}
            </button>
          ))}
          {notebook?.can_write && user ? (
            <button
              type="button"
              className="btn btn--small"
              onClick={() => void postJson('/api/notes/sections', { notebook_id: notebook.id, name: 'New section', csrf: user.csrf }).then(() => loadTree())}
            >
              Add section
            </button>
          ) : null}
        </div>
        <div className="onenote__work">
          <aside className="onenote__pages panel">
            <div className="row-actions">
              {notebook?.can_write ? (
                <>
                  <button type="button" className="btn btn--small btn--primary" onClick={() => void addPage('note')}>Add page</button>
                  <button type="button" className="btn btn--small" onClick={() => void addPage('list')}>Add list</button>
                </>
              ) : null}
            </div>
            {renderTree(null, 0)}
            {detail?.can_write && currentId ? (
              <button type="button" className="linkish" onClick={() => void addPage('note', currentId)}>Make subpage</button>
            ) : null}
          </aside>
          <section className="onenote__stage panel">
            {error ? <div className="status status--error">{error}</div> : null}
            {(conflict || hasDraft) ? (
              <div className="status status--error">
                {conflict ? 'Someone saved this page already. Your draft stayed on this device.' : 'A local draft is waiting.'}
                {user && detail ? (
                  <button type="button" className="btn btn--small" onClick={() => {
                    let raw = ''
                    try { raw = localStorage.getItem(`aa.note.draft.${detail.page.id}`) || '' } catch { raw = '' }
                    const draft = raw ? JSON.parse(raw) as { title?: string; body_html?: string; body_json?: string } : {}
                    void postJson<{ page: { id: number } }>(`/api/notes/pages/${detail.page.id}/recover-draft`, {
                      csrf: user.csrf,
                      title: draft.title || title,
                      body_html: draft.body_html || '',
                      body_json: draft.body_json || '',
                    }).then((row) => {
                      try { localStorage.removeItem(`aa.note.draft.${detail.page.id}`) } catch { /* ignore */ }
                      setHasDraft(false)
                      setConflict(false)
                      void loadTree()
                      navigate(`/notes/${row.page.id}`)
                    })
                  }}>Recover draft as a new page</button>
                ) : null}
              </div>
            ) : null}
            {!detail ? (
              <p className="muted">Pick a page, or add one in this section.</p>
            ) : (
              <>
                <div className="onenote__head">
                  <input className="input onenote__title" value={title} disabled={!detail.can_write} onChange={(e) => saveTitle(e.target.value)} />
                  <p className="muted">{detail.page.scope === 'school' ? 'Family can read this' : detail.page.scope === 'class' ? 'This class can read this' : 'Only you'}</p>
                </div>
                <div className="row-actions">
                  <button type="button" className="btn btn--small" onClick={() => {
                    const next = !hideFmt
                    setHideFmt(next)
                    try { localStorage.setItem('aa.notes.hideFmt', next ? '1' : '0') } catch { /* ignore */ }
                  }}>{hideFmt ? 'Show formatting' : 'Hide formatting'}</button>
                </div>
                {!hideFmt ? (
                  <NoteToolbar
                    pageId={detail.page.id}
                    canWrite={detail.can_write}
                    onMakeTask={() => setMakeTitle(title)}
                    onImage={() => undefined}
                  />
                ) : null}
                <div className="row-actions">
                  {detail.can_write && user?.is_teacher ? (
                    <button type="button" className="btn btn--small" onClick={() => setShareOpen(true)}>Who can see this</button>
                  ) : null}
                  <button type="button" className="btn btn--small" onClick={() => {
                    api<{ tasks: { id: number; title: string }[] }>('/api/tasks?filter=mine').then((data) => {
                      setOpenTasks(data.tasks)
                      setBringOpen(true)
                    })
                  }}>Bring in tasks</button>
                  <button type="button" className="btn btn--small" onClick={() => {
                    api<{ history: { id: number; title: string; created_at: string }[] }>(`/api/notes/pages/${detail.page.id}/history`).then((data) => setHistory(data.history))
                  }}>History</button>
                  <button type="button" className="btn btn--small" onClick={() => navigate(`/reminders?attach=page&item=${detail.page.id}`)}>Remind me</button>
                  {detail.can_write ? <button type="button" className="linkish" onClick={() => setDrop(detail.page)}>Move to trash</button> : null}
                </div>
                <BoxCanvas
                  pageId={detail.page.id}
                  title={title}
                  boxes={detail.boxes.filter((b) => b.id > 0)}
                  canWrite={detail.can_write}
                  onBoxes={(boxes) => setDetail((cur) => (cur ? { ...cur, boxes } : cur))}
                  onConflict={() => setConflict(true)}
                />
                {detail.tasks.length ? (
                  <ul className="plain-list">
                    {detail.tasks.map((t) => (
                      <li key={t.id}>
                        {t.completed ? 'Done · ' : ''}{t.title}
                        {detail.can_write && user ? (
                          <button type="button" className="linkish" onClick={() => {
                            void postJson(`/api/notes/pages/${detail.page.id}/unlink-task/${t.id}`, { csrf: user.csrf }).then(() => loadPage(detail.page.id))
                          }}>Unlink</button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            )}
          </section>
        </div>
      </div>
      {drop && user ? (
        <Confirm title="Move this page to trash?" message={drop.title} confirmLabel="Trash" onCancel={() => setDrop(null)} onConfirm={() => {
          void postJson(`/api/notes/pages/${drop.id}/delete`, { csrf: user.csrf }).then(() => {
            setDrop(null)
            void loadTree()
            navigate('/notes')
          })
        }} />
      ) : null}
      {makeTitle && user && detail ? (
        <Modal title="Make a to-do from this note" onClose={() => setMakeTitle('')} actions={
          <>
            <button type="button" className="btn" onClick={() => setMakeTitle('')}>Cancel</button>
            <button type="button" className="btn btn--primary" onClick={() => {
              void postJson(`/api/notes/pages/${detail.page.id}/make-task`, {
                title: makeTitle, due: makeDue, scope: detail.page.scope, course_id: detail.page.course_id || 0, csrf: user.csrf,
              }).then(() => { setMakeTitle(''); setMakeDue(''); void loadPage(detail.page.id) })
            }}>Make task</button>
          </>
        }>
          <label className="field"><span className="field__label">To-do</span><input className="input" value={makeTitle} onChange={(e) => setMakeTitle(e.target.value)} /></label>
          <label className="field"><span className="field__label">Due</span><input className="input" value={makeDue} onChange={(e) => setMakeDue(e.target.value)} placeholder="today or fri 3pm" /></label>
        </Modal>
      ) : null}
      {bringOpen && user && detail ? (
        <Modal title="Bring in a to-do" onClose={() => setBringOpen(false)} actions={<button type="button" className="btn" onClick={() => setBringOpen(false)}>Close</button>}>
          {openTasks.map((t) => (
            <button key={t.id} type="button" className="btn btn--small" onClick={() => {
              void postJson(`/api/notes/pages/${detail.page.id}/bring-in-task`, { task_id: t.id, csrf: user.csrf }).then(() => {
                setBringOpen(false)
                void loadPage(detail.page.id)
              })
            }}>{t.title}</button>
          ))}
        </Modal>
      ) : null}
      {shareOpen && user && detail ? (
        <Modal title="Who can see this page" onClose={() => setShareOpen(false)} actions={
          <>
            <button type="button" className="btn" onClick={() => setShareOpen(false)}>Cancel</button>
            <button type="button" className="btn btn--primary" onClick={() => {
              void postJson(`/api/notes/pages/${detail.page.id}/share`, { scope: shareScope, course_id: shareCourse, csrf: user.csrf }).then(() => {
                setShareOpen(false)
                void loadPage(detail.page.id)
              })
            }}>Save</button>
          </>
        }>
          <label className="field">
            <span className="field__label">Visibility</span>
            <select className="input" value={shareScope} onChange={(e) => setShareScope(e.target.value)}>
              <option value="personal">Only me</option>
              <option value="school">Whole family</option>
              <option value="class">This class</option>
            </select>
          </label>
          {shareScope === 'class' ? (
            <label className="field">
              <span className="field__label">Which class</span>
              <select className="input" value={shareCourse} onChange={(e) => setShareCourse(Number(e.target.value))}>
                <option value={0}>Pick a class</option>
                {courses.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
              </select>
            </label>
          ) : null}
        </Modal>
      ) : null}
      {renameSec && user ? (
        <Modal title="Rename this section" onClose={() => setRenameSec(null)} actions={
          <>
            <button type="button" className="btn" onClick={() => setRenameSec(null)}>Cancel</button>
            <button type="button" className="btn btn--primary" onClick={() => {
              void postJson(`/api/notes/sections/${renameSec.id}`, { name: renameVal, color: secColor, csrf: user.csrf }).then(() => {
                setRenameSec(null)
                void loadTree()
              })
            }}>Save</button>
          </>
        }>
          <label className="field"><span className="field__label">Name</span>
            <input className="input" value={renameVal} onChange={(e) => setRenameVal(e.target.value)} />
          </label>
          <label className="field"><span className="field__label">Tab color</span>
            <input className="input" type="color" value={secColor} onChange={(e) => setSecColor(e.target.value)} />
          </label>
          {(notebook?.sections.length || 0) > 1 ? (
            <p><button type="button" className="linkish" onClick={() => { setDropSec(renameSec); setRenameSec(null) }}>Delete this section</button></p>
          ) : <p className="muted">Keep at least one section.</p>}
        </Modal>
      ) : null}
      {bookEdit && user && notebook ? (
        <Modal title="Notebook" onClose={() => setBookEdit(false)} actions={
          <>
            <button type="button" className="btn" onClick={() => setBookEdit(false)}>Cancel</button>
            <button type="button" className="btn btn--primary" onClick={() => {
              void postJson(`/api/notes/notebooks/${notebook.id}`, { name: bookName, color: bookColor, csrf: user.csrf }).then(() => {
                setBookEdit(false)
                void loadTree()
              })
            }}>Save</button>
          </>
        }>
          <label className="field"><span className="field__label">Name</span>
            <input className="input" value={bookName} onChange={(e) => setBookName(e.target.value)} />
          </label>
          <label className="field"><span className="field__label">Color</span>
            <input className="input" type="color" value={bookColor} onChange={(e) => setBookColor(e.target.value)} />
          </label>
          <p>
            <button type="button" className="btn btn--small" onClick={() => {
              void postJson(`/api/notes/notebooks/${notebook.id}`, { archived: true, csrf: user.csrf }).then(() => {
                setBookEdit(false)
                setNotebookId(0)
                void loadTree()
              })
            }}>Archive notebook</button>
          </p>
          <p><button type="button" className="linkish" onClick={() => setDropBook(true)}>Delete notebook</button></p>
        </Modal>
      ) : null}
      {dropBook && user && notebook ? (
        <Confirm title="Delete this notebook?" message={notebook.name} confirmLabel="Delete" onCancel={() => setDropBook(false)} onConfirm={() => {
          void postJson(`/api/notes/notebooks/${notebook.id}/delete`, { csrf: user.csrf }).then(() => {
            setDropBook(false)
            setBookEdit(false)
            setNotebookId(0)
            void loadTree()
            navigate('/notes')
          })
        }} />
      ) : null}
      {dropSec && user ? (
        <Confirm title="Delete this section?" message={`${dropSec.name} and its pages go to trash.`} confirmLabel="Delete" onCancel={() => setDropSec(null)} onConfirm={() => {
          void postJson(`/api/notes/sections/${dropSec.id}/delete`, { csrf: user.csrf }).then(() => {
            setDropSec(null)
            void loadTree()
          })
        }} />
      ) : null}
      {history && user && detail ? (
        <Modal title="Earlier versions" onClose={() => setHistory(null)} actions={<button type="button" className="btn" onClick={() => setHistory(null)}>Close</button>}>
          {history.map((h) => (
            <div key={h.id} className="task-row">
              <span className="wrap-any">{h.title}</span>
              <button type="button" className="btn btn--small" onClick={() => {
                void postJson(`/api/notes/pages/${detail.page.id}/history/${h.id}/restore`, { csrf: user.csrf }).then(() => {
                  setHistory(null)
                  void loadPage(detail.page.id)
                })
              }}>Put this back</button>
            </div>
          ))}
        </Modal>
      ) : null}
    </div>
  )
}
