import { useEffect, useState, type DragEvent, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import type { DocEntry, DocListing } from '../types'
import { Confirm } from '../ui/Confirm'
import { Modal } from '../ui/Modal'

export function Documents() {
  const { user } = useAuth()
  const [listing, setListing] = useState<DocListing | null>(null)
  const [path, setPath] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [over, setOver] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [folderOpen, setFolderOpen] = useState(false)
  const [folderName, setFolderName] = useState('')
  const [dropAsk, setDropAsk] = useState(false)

  const load = async (rel = path) => {
    const data = await api<DocListing>(`/api/documents?path=${encodeURIComponent(rel)}`)
    setListing(data)
    setPath(data.rel)
    setSelected([])
  }

  useEffect(() => {
    load('').catch((err) => setError(err instanceof ApiError ? err.message : 'Could not open Documents.'))
  }, [])

  const toggle = (rel: string) => {
    setSelected((cur) => (cur.includes(rel) ? cur.filter((p) => p !== rel) : [...cur, rel]))
  }

  const upload = async (files: FileList | File[]) => {
    if (!user || !files.length) return
    const body = new FormData()
    body.set('parent', path)
    body.set('csrf', user.csrf)
    Array.from(files).forEach((f) => body.append('files', f))
    try {
      await api('/api/documents/upload', { method: 'POST', body })
      setOk('Saved.')
      setAddOpen(false)
      await load(path)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save those files.')
    }
  }

  const makeFolder = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    const body = new FormData()
    body.set('parent', path)
    body.set('name', folderName)
    body.set('csrf', user.csrf)
    try {
      await api('/api/documents/folder', { method: 'POST', body })
      setFolderName('')
      setFolderOpen(false)
      await load(path)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not make that folder.')
    }
  }

  const onDropFiles = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    if (e.dataTransfer.files.length) void upload(e.dataTransfer.files)
    const dest = (e.currentTarget as HTMLElement).getAttribute('data-dest')
    const dragged = e.dataTransfer.getData('text/paths')
    if (dragged && dest != null) {
      setSelected(dragged.split('\n').filter(Boolean))
      void postJson('/api/documents/move', { paths: dragged.split('\n').filter(Boolean), dest, csrf: user?.csrf || '' }).then(() => load(path))
    }
  }

  const items = listing ? [...listing.folders, ...listing.files] : []

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Documents</h1>
          <p className="muted">Folders on the left. Drop files here, or drag items into a folder.</p>
        </div>
        <div className="page-head__actions">
          <Link className="btn" to="/photos">Add photos</Link>
          <button type="button" className="btn" onClick={() => setFolderOpen(true)}>New folder</button>
          <button type="button" className="btn btn--primary" onClick={() => setAddOpen(true)}>Add documents</button>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {ok ? <div className="status status--ok">{ok}</div> : null}
      {listing ? (
        <p className="docs-crumbs wrap-any">
          {listing.crumbs.map((c, i) => (
            <span key={`${c.label}-${i}`}>
              {i ? <span className="docs-crumbs__sep"> / </span> : null}
              {c.href || i < listing.crumbs.length - 1 ? (
                <button type="button" className="linkish" onClick={() => void load(i === 0 ? '' : listing.destinations.find((d) => d.label.endsWith(c.label))?.rel || '')}>
                  {c.label}
                </button>
              ) : (
                c.label
              )}
            </span>
          ))}
        </p>
      ) : null}

      {selected.length ? (
        <div className="docs-toolbar">
          <span>{selected.length} selected</span>
          <label className="field docs-filter-field">
            <span className="visually-hidden">Move to folder</span>
            <select
              className="input"
              defaultValue=""
              onChange={(e) => {
                const dest = e.target.value
                if (dest === '' || !user) return
                void postJson('/api/documents/move', { paths: selected, dest, csrf: user.csrf })
                  .then(() => { setOk('Moved.'); return load(path) })
                  .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not move those.'))
              }}
            >
              <option value="">Move to…</option>
              {(listing?.destinations || []).map((d) => (
                <option key={d.rel || 'root'} value={d.rel}>{d.label}</option>
              ))}
            </select>
          </label>
          <button type="button" className="btn btn--small" onClick={() => setDropAsk(true)}>Delete</button>
        </div>
      ) : null}

      <div className="explorer">
        <aside className="panel explorer-tree">
          <p className="eyebrow">Folders</p>
          {(listing?.destinations || []).map((d) => (
            <button
              key={d.rel || 'root'}
              type="button"
              className={`tree-item ${path === d.rel ? 'is-on' : ''}`}
              style={{ paddingLeft: `${0.45 + d.depth * 0.7}rem` }}
              onClick={() => void load(d.rel)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                const dragged = e.dataTransfer.getData('text/paths')
                if (dragged) void postJson('/api/documents/move', { paths: dragged.split('\n').filter(Boolean), dest: d.rel, csrf: user?.csrf || '' }).then(() => load(path))
              }}
            >
              {d.label.split(' / ').slice(-1)[0]}
            </button>
          ))}
        </aside>
        <section
          className={`panel explorer-pane explorer-drop ${over ? 'is-over' : ''}`}
          data-dest={path}
          onDragOver={(e) => { e.preventDefault(); setOver(true) }}
          onDragLeave={() => setOver(false)}
          onDrop={onDropFiles}
        >
          <p className="muted">Drop files to save them in this folder.</p>
          {items.map((item: DocEntry) => (
            <div
              key={item.rel}
              className={`explorer-row ${selected.includes(item.rel) ? 'is-selected' : ''}`}
              draggable
              onDragStart={(e) => {
                const paths = selected.includes(item.rel) ? selected : [item.rel]
                e.dataTransfer.setData('text/paths', paths.join('\n'))
                if (!selected.includes(item.rel)) setSelected(paths)
              }}
            >
              <input type="checkbox" checked={selected.includes(item.rel)} onChange={() => toggle(item.rel)} />
              <button
                type="button"
                className="docs-item"
                onClick={() => {
                  if (item.kind === 'folder') void load(item.rel)
                }}
              >
                <span className={`docs-badge docs-badge--${item.kind === 'folder' ? 'folder' : item.kind}`}>{item.badge}</span>
                <span className="docs-item__text">
                  <strong className="wrap-any">{item.label}</strong>
                  <span className="muted">{item.size_label || 'Folder'}</span>
                </span>
              </button>
              {item.download_href ? (
                <a className="docs-action" href={item.download_href}>Download</a>
              ) : null}
              {item.inline_href && item.kind !== 'folder' ? (
                <a className="docs-action" href={item.inline_href} target="_blank" rel="noreferrer">Open</a>
              ) : null}
            </div>
          ))}
          {!items.length ? <p className="muted">This folder is empty.</p> : null}
        </section>
      </div>

      {addOpen ? (
        <Modal title="Add documents" onClose={() => setAddOpen(false)}>
          <p className="muted">They go in {listing?.title || 'Documents'}.</p>
          <label className="field">
            <span className="field__label">Files</span>
            <input className="input" type="file" multiple onChange={(e) => e.target.files && void upload(e.target.files)} />
          </label>
        </Modal>
      ) : null}

      {folderOpen ? (
        <Modal title="New folder" onClose={() => setFolderOpen(false)}>
          <form className="form" onSubmit={(e) => void makeFolder(e)}>
            <label className="field">
              <span className="field__label">Folder name</span>
              <input className="input" value={folderName} onChange={(e) => setFolderName(e.target.value)} required autoFocus />
            </label>
            <button type="submit" className="btn btn--primary">Make folder</button>
          </form>
        </Modal>
      ) : null}

      {dropAsk && user ? (
        <Confirm
          title="Delete selected?"
          message="This cannot be undone."
          confirmLabel="Delete"
          onCancel={() => setDropAsk(false)}
          onConfirm={() => {
            void postJson('/api/documents/delete', { paths: selected, csrf: user.csrf }).then(() => {
              setDropAsk(false)
              void load(path)
            }).catch((err) => setError(err instanceof ApiError ? err.message : 'Could not delete.'))
          }}
        />
      ) : null}
    </>
  )
}
