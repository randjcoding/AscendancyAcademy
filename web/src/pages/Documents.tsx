import { useEffect, useRef, useState, type DragEvent, type FormEvent, type MouseEvent } from 'react'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import type { DocEntry, DocListing } from '../types'
import { Confirm } from '../ui/Confirm'
import { FolderIcon } from '../ui/FolderIcon'
import { Modal } from '../ui/Modal'

type Menu = { x: number; y: number; rel: string; label: string }

export function Documents() {
  const { user } = useAuth()
  const [listing, setListing] = useState<DocListing | null>(null)
  const [path, setPath] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [over, setOver] = useState(false)
  const [folderOpen, setFolderOpen] = useState(false)
  const [folderName, setFolderName] = useState('')
  const [target, setTarget] = useState('')
  const [dropAsk, setDropAsk] = useState(false)
  const [menu, setMenu] = useState<Menu | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = async (rel = path) => {
    const data = await api<DocListing>(`/api/documents?path=${encodeURIComponent(rel)}`)
    setListing(data)
    setPath(data.rel)
    setSelected([])
  }

  useEffect(() => {
    load('').catch((err) => setError(err instanceof ApiError ? err.message : 'Could not open Documents.'))
  }, [])

  useEffect(() => {
    const close = () => setMenu(null)
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])

  const toggle = (rel: string) => {
    setSelected((cur) => (cur.includes(rel) ? cur.filter((p) => p !== rel) : [...cur, rel]))
  }

  const upload = async (files: FileList | File[], parent = target || path) => {
    if (!user || !files.length) return
    const body = new FormData()
    body.set('parent', parent)
    body.set('csrf', user.csrf)
    Array.from(files).forEach((f) => body.append('files', f))
    try {
      await api('/api/documents/upload', { method: 'POST', body })
      setOk('Saved.')
      await load(path)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save those files.')
    }
  }

  const makeFolder = async (e: FormEvent) => {
    e.preventDefault()
    if (!user) return
    const body = new FormData()
    body.set('parent', target)
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
    if (e.dataTransfer.files.length) void upload(e.dataTransfer.files, path)
    const dest = (e.currentTarget as HTMLElement).getAttribute('data-dest')
    const dragged = e.dataTransfer.getData('text/paths')
    if (dragged && dest != null) {
      void postJson('/api/documents/move', { paths: dragged.split('\n').filter(Boolean), dest, csrf: user?.csrf || '' }).then(() => load(path))
    }
  }

  const openMenu = (e: MouseEvent, rel: string, label: string) => {
    e.preventDefault()
    e.stopPropagation()
    setMenu({ x: e.clientX, y: e.clientY, rel, label })
  }

  const startFolder = (rel: string) => {
    setTarget(rel)
    setFolderName('')
    setFolderOpen(true)
    setMenu(null)
  }

  const startFiles = (rel: string) => {
    setTarget(rel)
    setMenu(null)
    requestAnimationFrame(() => fileRef.current?.click())
  }

  const downloadSelected = async () => {
    if (!user || !selected.length) return
    try {
      const resp = await fetch('/api/documents/zip', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: selected, csrf: user.csrf }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ error: 'Could not download those files.' }))
        throw new ApiError(body.error || 'Could not download those files.', resp.status)
      }
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = selected.length === 1 ? 'download.zip' : 'documents.zip'
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not download those files.')
    }
  }

  const items = listing ? [...listing.folders, ...listing.files] : []

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Documents</h1>
          <p className="muted">Right-click a folder to add a subfolder or files. Pictures and papers go in the same place.</p>
        </div>
        <div className="page-head__actions">
          <button type="button" className="btn" onClick={() => startFolder(path)}>New folder</button>
          <button type="button" className="btn btn--primary" onClick={() => startFiles(path)}>Add files</button>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {ok ? <div className="status status--ok">{ok}</div> : null}
      <input
        ref={fileRef}
        className="visually-hidden"
        type="file"
        multiple
        onChange={(e) => {
          if (e.target.files) void upload(e.target.files, target)
          e.target.value = ''
        }}
      />
      {listing ? (
        <p className="docs-crumbs wrap-any">
          {listing.crumbs.map((c, i) => (
            <span key={`${c.label}-${i}`}>
              {i ? <span className="docs-crumbs__sep"> / </span> : null}
              {i === 0 || i < listing.crumbs.length - 1 ? (
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
          <button type="button" className="btn btn--small" onClick={() => void downloadSelected()}>
            Download
          </button>
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
        <aside className="panel explorer-tree" onContextMenu={(e) => openMenu(e, '', 'Documents')}>
          <p className="eyebrow">Folders</p>
          {(listing?.destinations || []).map((d) => (
            <button
              key={d.rel || 'root'}
              type="button"
              className={`tree-item ${path === d.rel ? 'is-on' : ''}`}
              style={{ paddingLeft: `${0.45 + d.depth * 0.7}rem` }}
              onClick={() => void load(d.rel)}
              onContextMenu={(e) => openMenu(e, d.rel, d.label.split(' / ').slice(-1)[0])}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                const dragged = e.dataTransfer.getData('text/paths')
                if (dragged) void postJson('/api/documents/move', { paths: dragged.split('\n').filter(Boolean), dest: d.rel, csrf: user?.csrf || '' }).then(() => load(path))
              }}
            >
              <FolderIcon />
              <span className="wrap-any">{d.label.split(' / ').slice(-1)[0]}</span>
            </button>
          ))}
        </aside>
        <section
          className={`panel explorer-pane explorer-drop ${over ? 'is-over' : ''}`}
          data-dest={path}
          onDragOver={(e) => { e.preventDefault(); setOver(true) }}
          onDragLeave={() => setOver(false)}
          onDrop={onDropFiles}
          onContextMenu={(e) => openMenu(e, path, listing?.title || 'Documents')}
        >
          <p className="muted">Drop files here, or right-click a folder.</p>
          {items.map((item: DocEntry) => (
            <div
              key={item.rel}
              className={`explorer-row ${selected.includes(item.rel) ? 'is-selected' : ''}`}
              draggable
              onContextMenu={(e) => {
                if (item.kind === 'folder') openMenu(e, item.rel, item.label)
              }}
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
                {item.kind === 'folder' ? (
                  <FolderIcon />
                ) : (
                  <span className={`docs-badge docs-badge--${item.kind}`}>{item.badge}</span>
                )}
                <span className="docs-item__name wrap-any">{item.label}</span>
              </button>
              {item.kind === 'folder' ? (
                <button type="button" className="docs-action" onClick={() => void load(item.rel)}>
                  Open
                </button>
              ) : (
                <span className="docs-actions">
                  {item.download_href ? <a className="docs-action" href={item.download_href}>Download</a> : null}
                  {item.inline_href ? <a className="docs-action" href={item.inline_href} target="_blank" rel="noreferrer">Open</a> : null}
                </span>
              )}
            </div>
          ))}
          {!items.length ? <p className="muted">This folder is empty.</p> : null}
        </section>
      </div>

      {menu ? (
        <div className="ctx-menu" style={{ left: menu.x, top: menu.y }} onClick={(e) => e.stopPropagation()}>
          <p className="ctx-menu__label wrap-any">{menu.label}</p>
          <button type="button" onClick={() => startFolder(menu.rel)}>New folder</button>
          <button type="button" onClick={() => startFiles(menu.rel)}>Add files</button>
        </div>
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
