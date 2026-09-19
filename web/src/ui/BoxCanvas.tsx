import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import TaskList from '@tiptap/extension-task-list'
import TaskItem from '@tiptap/extension-task-item'
import { Table } from '@tiptap/extension-table'
import { TableRow } from '@tiptap/extension-table-row'
import { TableCell } from '@tiptap/extension-table-cell'
import { TableHeader } from '@tiptap/extension-table-header'
import { TextStyle } from '@tiptap/extension-text-style'
import { Color } from '@tiptap/extension-color'
import { TextAlign } from '@tiptap/extension-text-align'
import { Extension, type Editor } from '@tiptap/core'
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Modal } from './Modal'

export type NoteBox = {
  id: number
  revision: number
  x: number
  y: number
  w: number
  h: number
  z: number
  bg: string
  body_html: string
}

const FontSize = Extension.create({
  name: 'fontSize',
  addGlobalAttributes() {
    return [{
      types: ['textStyle'],
      attributes: {
        fontSize: {
          default: null,
          parseHTML: (el) => (el as HTMLElement).style.fontSize || null,
          renderHTML: (attrs) => (attrs.fontSize ? { style: `font-size: ${attrs.fontSize}` } : {}),
        },
      },
    }]
  },
})

const Keys = Extension.create({
  name: 'boxKeys',
  addKeyboardShortcuts() {
    return {
      Tab: () => this.editor.commands.sinkListItem('taskItem') || this.editor.commands.sinkListItem('listItem'),
      'Shift-Tab': () => this.editor.commands.liftListItem('taskItem') || this.editor.commands.liftListItem('listItem'),
    }
  },
})

export type SelectedBoxCmds = {
  setBg: (bg: string) => void
  front: () => void
  back: () => void
  remove: () => void
  html: () => string
  setHtml: (html: string) => void
}

let selectedBoxCmds: SelectedBoxCmds | null = null
export function getSelectedBoxCmds() {
  return selectedBoxCmds
}

const CascadingTaskItem = TaskItem.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      collapsed: {
        default: false,
        parseHTML: (el) => el.getAttribute('data-collapsed') === 'true',
        renderHTML: (attrs) => (attrs.collapsed ? { 'data-collapsed': 'true' } : {}),
      },
    }
  },
})

function cascade(doc: { type?: string; attrs?: { checked?: boolean }; content?: unknown[] }, inherit = false) {
  const nodes = (doc.content || []) as { type?: string; attrs?: { checked?: boolean }; content?: unknown[] }[]
  for (const node of nodes) {
    if (node.type === 'taskItem') {
      if (inherit) node.attrs = { ...node.attrs, checked: true }
      cascade(node, Boolean(node.attrs?.checked))
    } else cascade(node, inherit)
  }
}

let activeEditor: Editor | null = null

export function getActiveEditor() {
  return activeEditor
}

const BOX_BGS = [
  { id: '', label: 'Paper' },
  { id: 'color-mix(in srgb, var(--gold) 22%, var(--surface))', label: 'Gold' },
  { id: 'color-mix(in srgb, var(--brand) 18%, var(--surface))', label: 'Brand' },
  { id: 'color-mix(in srgb, var(--present) 22%, var(--surface))', label: 'Green' },
  { id: 'color-mix(in srgb, var(--absent) 16%, var(--surface))', label: 'Rose' },
]

function BoxPane({
  box,
  selected,
  canWrite,
  onSelect,
  onChanged,
  onDelete,
  onConflict,
}: {
  box: NoteBox
  selected: boolean
  canWrite: boolean
  onSelect: () => void
  onChanged: (next: NoteBox) => void
  onDelete: () => void
  onConflict: () => void
}) {
  const { user } = useAuth()
  const rev = useRef(box.revision)
  const pending = useRef<Record<string, unknown> | null>(null)
  const timer = useRef<number | null>(null)
  const drag = useRef<{ mx: number; my: number; x: number; y: number; w: number; h: number; mode: 'move' | 'resize' } | null>(null)
  const [status, setStatus] = useState('')

  useEffect(() => {
    rev.current = box.revision
  }, [box.revision])

  const editor = useEditor(
    {
      extensions: [
        StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
        Underline,
        Link.configure({ openOnClick: false }),
        Image,
        Placeholder.configure({ placeholder: 'Type here' }),
        TaskList,
        CascadingTaskItem.configure({ nested: true }),
        Table.configure({ resizable: false }),
        TableRow,
        TableHeader,
        TableCell,
        TextStyle,
        FontSize,
        Color,
        TextAlign.configure({ types: ['heading', 'paragraph'] }),
        Keys,
      ],
      content: box.body_html || '<p></p>',
      editable: canWrite,
      editorProps: { attributes: { class: 'note-doc note-doc--box' } },
      onFocus: ({ editor: ed }) => { activeEditor = ed },
      onUpdate: ({ editor: ed }) => {
        if (!canWrite) return
        const json = structuredClone(ed.getJSON())
        const before = JSON.stringify(json)
        cascade(json)
        if (JSON.stringify(json) !== before) ed.commands.setContent(json, { emitUpdate: false })
        queue({ body_html: ed.getHTML(), body_json: JSON.stringify(ed.getJSON()) })
      },
    },
    [box.id, canWrite],
  )

  useEffect(() => {
    if (editor) editor.commands.setContent(box.body_html || '<p></p>', { emitUpdate: false })
  }, [editor, box.id])

  const flush = async (extra: Record<string, unknown> = {}) => {
    if (!user || !canWrite) return
    const payload = { ...(pending.current || {}), ...extra }
    pending.current = null
    try {
      const result = await postJson<{ box: NoteBox }>(`/api/notes/boxes/${box.id}`, {
        ...payload,
        csrf: user.csrf,
        revision: rev.current,
      })
      rev.current = result.box.revision
      onChanged(result.box)
      setStatus('Saved')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) onConflict()
      else setStatus('Not saved')
    }
  }

  const queue = (payload: Record<string, unknown>) => {
    pending.current = { ...(pending.current || {}), ...payload }
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => void flush(), 600)
  }

  useEffect(() => {
    if (!selected) return
    selectedBoxCmds = {
      setBg: (bg) => {
        onChanged({ ...box, bg })
        void flush({ bg })
      },
      front: () => void flush({ z: box.z + 5 }),
      back: () => void flush({ z: Math.max(0, box.z - 5) }),
      remove: () => onDelete(),
      html: () => editor?.getHTML() || box.body_html || '',
      setHtml: (html) => {
        editor?.commands.setContent(html || '<p></p>')
        queue({ body_html: html, body_json: JSON.stringify(editor?.getJSON() || {}) })
      },
    }
    return () => {
      selectedBoxCmds = null
    }
  }, [selected, box, editor])

  const geom = useRef({ x: box.x, y: box.y, w: box.w, h: box.h })
  useEffect(() => {
    geom.current = { x: box.x, y: box.y, w: box.w, h: box.h }
  }, [box.x, box.y, box.w, box.h])

  const onPointer = (mode: 'move' | 'resize', e: ReactPointerEvent) => {
    if (!canWrite) return
    e.preventDefault()
    e.stopPropagation()
    onSelect()
    drag.current = { mx: e.clientX, my: e.clientY, x: box.x, y: box.y, w: box.w, h: box.h, mode }
    const move = (ev: PointerEvent) => {
      if (!drag.current) return
      const dx = ev.clientX - drag.current.mx
      const dy = ev.clientY - drag.current.my
      const next =
        drag.current.mode === 'move'
          ? { x: Math.max(0, drag.current.x + dx), y: Math.max(0, drag.current.y + dy) }
          : { w: Math.max(160, drag.current.w + dx), h: Math.max(80, drag.current.h + dy) }
      geom.current = { ...geom.current, ...next }
      onChanged({ ...box, ...geom.current })
    }
    const up = () => {
      document.removeEventListener('pointermove', move)
      document.removeEventListener('pointerup', up)
      drag.current = null
      void flush({ ...geom.current })
    }
    document.addEventListener('pointermove', move)
    document.addEventListener('pointerup', up)
  }

  return (
    <article
      className={`nbox ${selected ? 'is-on' : ''}`}
      style={{
        left: box.x,
        top: box.y,
        width: box.w,
        minHeight: box.h,
        zIndex: box.z,
        background: box.bg || 'var(--surface)',
      }}
      onPointerDown={() => onSelect()}
    >
      {canWrite ? (
        <div className="nbox__bar">
          <button type="button" className="nbox__grip" onPointerDown={(e) => onPointer('move', e)}>
            Move
          </button>
          {status ? <span className="muted">{status}</span> : null}
          <select
            className="input"
            value={box.bg || ''}
            aria-label="Box color"
            onChange={(e) => {
              const bg = e.target.value
              onChanged({ ...box, bg })
              void flush({ bg })
            }}
          >
            {BOX_BGS.map((bg) => <option key={bg.label} value={bg.id}>{bg.label}</option>)}
          </select>
          <button type="button" className="btn btn--small" onClick={() => void flush({ z: box.z + 5 })}>Front</button>
          <button type="button" className="linkish" onClick={onDelete}>Delete box</button>
        </div>
      ) : null}
      {editor && selected && canWrite ? <EditorContent editor={editor} /> : (
        <div className="note-doc note-doc--box" dangerouslySetInnerHTML={{ __html: box.body_html || '<p></p>' }} />
      )}
      {canWrite ? <span className="nbox__resize" onPointerDown={(e) => onPointer('resize', e)} /> : null}
    </article>
  )
}

export function NoteToolbar({
  pageId,
  canWrite,
  onMakeTask,
  onImage,
}: {
  pageId: number
  canWrite: boolean
  onMakeTask: () => void
  onImage: (url: string) => void
}) {
  const { user } = useAuth()
  const [linkOpen, setLinkOpen] = useState(false)
  const [linkUrl, setLinkUrl] = useState('https://')
  if (!canWrite) return null
  const ed = () => getActiveEditor()
  return (
    <div className="note-toolbar" role="toolbar">
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().toggleBold().run()}>Bold</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().toggleItalic().run()}>Italic</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().toggleUnderline().run()}>Underline</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().toggleStrike().run()}>Strike</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().toggleHeading({ level: 2 }).run()}>Heading</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().toggleBulletList().run()}>Bullets</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().toggleOrderedList().run()}>Numbers</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().toggleTaskList().run()}>Checks</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().sinkListItem('taskItem').run()}>Indent</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().liftListItem('taskItem').run()}>Outdent</button>
      <button type="button" className="btn btn--small" onClick={() => {
        const cur = ed()?.getAttributes('taskItem')
        ed()?.commands.updateAttributes('taskItem', { collapsed: !cur?.collapsed })
      }}>Fold</button>
      <label className="btn btn--small">
        Color
        <input hidden type="color" onChange={(e) => ed()?.chain().focus().setColor(e.target.value).run()} />
      </label>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().setTextAlign('left').run()}>Left</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().setTextAlign('center').run()}>Center</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().setTextAlign('right').run()}>Right</button>
      <button type="button" className="btn btn--small" onClick={() => {
        const text = window.getSelection()?.toString() || ''
        if (text) document.execCommand('insertText', false, text.toUpperCase())
      }}>ABC</button>
      <button type="button" className="btn btn--small" onClick={() => {
        const text = window.getSelection()?.toString() || ''
        if (text) document.execCommand('insertText', false, text.toLowerCase())
      }}>abc</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().setHorizontalRule().run()}>Line</button>
      <button type="button" className="btn btn--small" onClick={() => ed()?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>Table</button>
      <button type="button" className="btn btn--small" onClick={() => { setLinkUrl('https://'); setLinkOpen(true) }}>Link</button>
      <label className="btn btn--small">
        Picture
        <input
          hidden
          type="file"
          accept="image/*"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (!file || !user) return
            const body = new FormData()
            body.set('file', file)
            void fetch(`/api/notes/pages/${pageId}/upload`, { method: 'POST', body, credentials: 'same-origin' })
              .then((r) => r.json())
              .then((data) => {
                  if (data.url) {
                  ed()?.chain().focus().setImage({ src: data.url }).run()
                  onImage(data.url)
                }
              })
            e.target.value = ''
          }}
        />
      </label>
      <button type="button" className="btn btn--small btn--primary" onClick={onMakeTask}>Make task</button>
      {linkOpen ? (
        <Modal title="Add a link" onClose={() => setLinkOpen(false)} actions={
          <>
            <button type="button" className="btn" onClick={() => setLinkOpen(false)}>Cancel</button>
            <button type="button" className="btn btn--primary" onClick={() => {
              if (linkUrl.trim()) ed()?.chain().focus().setLink({ href: linkUrl.trim() }).run()
              setLinkOpen(false)
            }}>Add</button>
          </>
        }>
          <label className="field"><span className="field__label">Address</span>
            <input className="input" value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} />
          </label>
        </Modal>
      ) : null}
    </div>
  )
}

function rememberDraft(pageId: number, title: string, boxes: NoteBox[]) {
  try {
    localStorage.setItem(`aa.note.draft.${pageId}`, JSON.stringify({
      title,
      body_html: boxes.map((b) => b.body_html || '').join('\n'),
      body_json: JSON.stringify({ boxes }),
    }))
  } catch { /* ignore */ }
}

export function BoxCanvas({
  pageId,
  title,
  boxes,
  canWrite,
  onBoxes,
  onConflict,
}: {
  pageId: number
  title: string
  boxes: NoteBox[]
  canWrite: boolean
  onBoxes: (boxes: NoteBox[]) => void
  onConflict: () => void
}) {
  const { user } = useAuth()
  const [sel, setSel] = useState<number | null>(boxes[0]?.id || null)

  const addAt = async (x: number, y: number) => {
    if (!user || !canWrite) return
    const created = await postJson<{ box: NoteBox }>(`/api/notes/pages/${pageId}/boxes`, { csrf: user.csrf, x, y })
    const next = [...boxes, created.box]
    onBoxes(next)
    rememberDraft(pageId, title, next)
    setSel(created.box.id)
  }

  const removeBox = async (id: number) => {
    if (!user) return
    await postJson(`/api/notes/boxes/${id}/delete`, { csrf: user.csrf })
    const next = boxes.filter((b) => b.id !== id)
    onBoxes(next)
    rememberDraft(pageId, title, next)
    if (sel === id) setSel(next[0]?.id || null)
  }

  return (
    <div
      className="note-canvas"
      onDoubleClick={(e) => {
        if (!canWrite) return
        const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect()
        void addAt(e.clientX - rect.left + (e.currentTarget as HTMLDivElement).scrollLeft, e.clientY - rect.top + (e.currentTarget as HTMLDivElement).scrollTop)
      }}
    >
      {!boxes.length ? <p className="muted note-canvas__hint">Double-click anywhere to start a box.</p> : null}
      {boxes.map((box) => (
        <BoxPane
          key={box.id}
          box={box}
          selected={sel === box.id}
          canWrite={canWrite}
          onSelect={() => setSel(box.id)}
          onChanged={(next) => {
            const all = boxes.map((b) => (b.id === next.id ? next : b))
            onBoxes(all)
            rememberDraft(pageId, title, all)
          }}
          onDelete={() => void removeBox(box.id)}
          onConflict={onConflict}
        />
      ))}
    </div>
  )
}
