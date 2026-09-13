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
import { Extension } from '@tiptap/core'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, postJson } from '../api'
import { useAuth } from '../Auth'
import { Modal } from './Modal'

const ChecklistKeys = Extension.create({
  name: 'checklistKeys',
  addKeyboardShortcuts() {
    return {
      Tab: () => this.editor.commands.sinkListItem('taskItem') || this.editor.commands.sinkListItem('listItem'),
      'Shift-Tab': () => this.editor.commands.liftListItem('taskItem') || this.editor.commands.liftListItem('listItem'),
    }
  },
})

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

function cascadeChecked(doc: { type?: string; attrs?: { checked?: boolean }; content?: unknown[] }, inherit = false) {
  if (!doc) return
  const nodes = (doc.content || []) as { type?: string; attrs?: { checked?: boolean; collapsed?: boolean }; content?: unknown[] }[]
  for (const node of nodes) {
    if (node.type === 'taskItem') {
      if (inherit) node.attrs = { ...node.attrs, checked: true }
      cascadeChecked(node, Boolean(node.attrs?.checked))
    } else {
      cascadeChecked(node, inherit)
    }
  }
}

type SaveResult = { ok?: boolean; revision: number; title?: string; error?: string }

export function NoteEditor({
  pageId,
  title,
  bodyHtml,
  revision,
  canWrite,
  onTitle,
  onSaved,
  onMakeTask,
}: {
  pageId: number
  title: string
  bodyHtml: string
  revision: number
  canWrite: boolean
  onTitle: (value: string) => void
  onSaved: (revision: number, title: string) => void
  onMakeTask: (text: string) => void
}) {
  const { user } = useAuth()
  const visit = useMemo(() => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())), [])
  const draftKey = `aa.drafts.${user?.id || 0}.${pageId}.${visit}`
  const revisionRef = useRef(revision)
  const queue = useRef<{ pending: Record<string, unknown> | null; running: boolean; conflict: boolean }>({
    pending: null,
    running: false,
    conflict: false,
  })
  const [status, setStatus] = useState('All changes saved')
  const [linkOpen, setLinkOpen] = useState(false)
  const [linkUrl, setLinkUrl] = useState('https://')
  const skip = useRef(true)

  useEffect(() => {
    revisionRef.current = revision
  }, [revision])

  const editor = useEditor(
    {
      extensions: [
        StarterKit.configure({ heading: { levels: [2, 3] } }),
        Underline,
        Link.configure({ openOnClick: false }),
        Image,
        Placeholder.configure({ placeholder: 'Write here. Tab indents a list.' }),
        TaskList,
        CascadingTaskItem.configure({ nested: true }),
        Table.configure({ resizable: false }),
        TableRow,
        TableHeader,
        TableCell,
        ChecklistKeys,
      ],
      content: bodyHtml || '<p></p>',
      editable: canWrite,
      editorProps: { attributes: { class: 'note-doc' } },
      onUpdate: ({ editor: ed }) => {
        if (!canWrite) return
        const json = structuredClone(ed.getJSON())
        const before = JSON.stringify(json)
        cascadeChecked(json)
        if (JSON.stringify(json) !== before) {
          ed.commands.setContent(json, { emitUpdate: false })
        }
        const html = ed.getHTML()
        persistDraft(title, html, json)
        scheduleSave(title, html, json)
      },
    },
    [pageId, canWrite],
  )

  useEffect(() => {
    if (!editor) return
    skip.current = true
    editor.commands.setContent(bodyHtml || '<p></p>', { emitUpdate: false })
    queue.current = { pending: null, running: false, conflict: false }
    setStatus('All changes saved')
  }, [editor, pageId, bodyHtml])

  const persistDraft = (nextTitle: string, html: string, json: unknown) => {
    try {
      localStorage.setItem(draftKey, JSON.stringify({ title: nextTitle, body_html: html, body_json: json, time: Date.now() }))
    } catch {
      setStatus('Local draft storage is unavailable. Keep this page open until saved.')
    }
  }

  const runSave = async () => {
    if (!user || queue.current.running || queue.current.conflict || !queue.current.pending) return
    const payload = queue.current.pending
    queue.current.pending = null
    queue.current.running = true
    setStatus('Saving…')
    try {
      const result = await postJson<SaveResult>(`/api/notes/pages/${pageId}/save`, {
        ...payload,
        csrf: user.csrf,
        revision: revisionRef.current,
      })
      revisionRef.current = result.revision
      onSaved(result.revision, result.title || title)
      try {
        localStorage.removeItem(draftKey)
      } catch {
        /* keep going */
      }
      setStatus('All changes saved')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        queue.current.conflict = true
        setStatus('Save conflict — your draft is kept on this device.')
      } else {
        queue.current.pending = queue.current.pending || payload
        setStatus('Not saved — draft kept on this device. Check connection and retry.')
      }
    } finally {
      queue.current.running = false
      if (queue.current.pending && !queue.current.conflict) void runSave()
    }
  }

  const timer = useRef<number | null>(null)
  const scheduleSave = (nextTitle: string, html: string, json: unknown) => {
    if (!canWrite) return
    queue.current.pending = { title: nextTitle, body_html: html, body_json: JSON.stringify(json) }
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => void runSave(), 700)
  }

  const changeTitle = (value: string) => {
    onTitle(value)
    if (!editor) return
    persistDraft(value, editor.getHTML(), editor.getJSON())
    scheduleSave(value, editor.getHTML(), editor.getJSON())
  }

  const addImage = async (file: File) => {
    if (!user) return
    const body = new FormData()
    body.set('file', file)
    const resp = await fetch(`/api/notes/pages/${pageId}/upload`, { method: 'POST', body, credentials: 'same-origin' })
    const data = await resp.json()
    if (data.url) editor?.chain().focus().setImage({ src: data.url }).run()
  }

  if (!editor) return <p className="muted">Loading the page…</p>

  return (
    <div className={`note-editor ${queue.current.conflict ? 'is-conflict' : ''}`}>
      <label className="field">
        <span className="field__label">Title</span>
        <input className="input" value={title} onChange={(e) => changeTitle(e.target.value)} disabled={!canWrite} />
      </label>
      {canWrite ? (
        <div className="note-toolbar" role="toolbar">
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().toggleBold().run()}>Bold</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().toggleItalic().run()}>Italic</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().toggleUnderline().run()}>Underline</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>Heading</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().toggleBulletList().run()}>Bullets</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().toggleOrderedList().run()}>Numbers</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().toggleTaskList().run()}>Checks</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().sinkListItem('taskItem').run()}>Indent</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().liftListItem('taskItem').run()}>Outdent</button>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().updateAttributes('taskItem', { collapsed: !editor.getAttributes('taskItem').collapsed }).run()}>
            Fold
          </button>
          <button type="button" className="btn btn--small" onClick={() => { setLinkUrl(editor.getAttributes('link').href || 'https://'); setLinkOpen(true) }}>
            Link
          </button>
          <label className="btn btn--small">
            Picture
            <input hidden type="file" accept="image/*" onChange={(e) => { const f = e.target.files?.[0]; if (f) void addImage(f); e.target.value = '' }} />
          </label>
          <button type="button" className="btn btn--small" onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>
            Table
          </button>
          <button
            type="button"
            className="btn btn--small btn--primary"
            onClick={() => {
              const text = editor.state.doc.textBetween(editor.state.selection.from, editor.state.selection.to, ' ').trim()
              onMakeTask(text || title)
            }}
          >
            Make task
          </button>
        </div>
      ) : (
        <p className="muted">You can read this page. Checking off to-dos still works on To-do.</p>
      )}
      <EditorContent editor={editor} />
      <p className="muted note-save-status">{status}</p>
      {linkOpen ? (
        <Modal
          title="Add a link"
          onClose={() => setLinkOpen(false)}
          actions={
            <>
              <button type="button" className="btn" onClick={() => setLinkOpen(false)}>Cancel</button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => {
                  if (linkUrl.trim()) editor.chain().focus().setLink({ href: linkUrl.trim() }).run()
                  setLinkOpen(false)
                }}
              >
                Add
              </button>
            </>
          }
        >
          <label className="field">
            <span className="field__label">Address</span>
            <input className="input" value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} />
          </label>
        </Modal>
      ) : null}
    </div>
  )
}
