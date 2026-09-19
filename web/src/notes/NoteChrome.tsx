import { useEffect, useState, type ReactNode } from 'react'
import { getActiveEditor } from '../ui/BoxCanvas'
import { Modal } from '../ui/Modal'

const SIZES = [10, 12, 14, 15, 16, 18, 20, 22, 24, 28, 32, 40, 48, 64]
const BOX_PRESETS = [
  { id: '', label: 'Paper' },
  { id: 'color-mix(in srgb, var(--gold) 22%, var(--surface))', label: 'Gold' },
  { id: 'color-mix(in srgb, var(--brand) 18%, var(--surface))', label: 'Brand' },
  { id: 'color-mix(in srgb, var(--present) 22%, var(--surface))', label: 'Green' },
  { id: 'color-mix(in srgb, var(--absent) 16%, var(--surface))', label: 'Rose' },
]

function applyCase(kind: 'upper' | 'lower' | 'camel' | 'sentence') {
  const ed = getActiveEditor()
  if (!ed) return
  const { from, to } = ed.state.selection
  const text = ed.state.doc.textBetween(from, to, ' ')
  if (!text) return
  let next = text
  if (kind === 'upper') next = text.toUpperCase()
  if (kind === 'lower') next = text.toLowerCase()
  if (kind === 'camel') {
    next = text
      .replace(/[^A-Za-z0-9]+(.)/g, (_, c: string) => c.toUpperCase())
      .replace(/^./, (c) => c.toLowerCase())
  }
  if (kind === 'sentence') next = text.toLowerCase().replace(/^\s*[a-z]/, (c) => c.toUpperCase())
  ed.chain().focus().insertContent(next).run()
}

function Drop({
  id,
  label,
  title,
  children,
}: {
  id: string
  label: string
  title?: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      const root = document.getElementById(id)
      if (root && !root.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open, id])
  return (
    <div className="fmt-drop" id={id}>
      <button type="button" className="fmt-drop__btn" title={title} onClick={() => setOpen((v) => !v)}>
        {label} ▾
      </button>
      {open ? (
        <div className="fmt-drop__menu" onClick={() => setOpen(false)}>
          {children}
        </div>
      ) : null}
    </div>
  )
}

export function NoteChrome({
  canWrite,
  hideFmt,
  hideMenubar,
  compact,
  hasDraft,
  conflict,
  pageId,
  pageTitle,
  pages,
  parentId,
  onHideFmt,
  onHideMenubar,
  onCompact,
  onHistory,
  onRecover,
  onRetry,
  onTrash,
  onRemind,
  onMakeTask,
  onBringTasks,
  onParent,
  onBoxBg,
  onBoxFront,
  onBoxBack,
  onBoxDelete,
  onBoxRemind,
  onSource,
}: {
  canWrite: boolean
  hideFmt: boolean
  hideMenubar: boolean
  compact: boolean
  hasDraft: boolean
  conflict: boolean
  pageId: number
  pageTitle: string
  pages: { id: number; title: string }[]
  parentId: number | null
  onHideFmt: (v: boolean) => void
  onHideMenubar: (v: boolean) => void
  onCompact: (v: boolean) => void
  onHistory: () => void
  onRecover: () => void
  onRetry: () => void
  onTrash: () => void
  onRemind: () => void
  onMakeTask: () => void
  onBringTasks: () => void
  onParent: (id: number) => void
  onBoxBg: (bg: string) => void
  onBoxFront: () => void
  onBoxBack: () => void
  onBoxDelete: () => void
  onBoxRemind: () => void
  onSource: () => void
}) {
  const [menu, setMenu] = useState('')
  const [linkOpen, setLinkOpen] = useState(false)
  const [linkUrl, setLinkUrl] = useState('https://')
  const [mobile, setMobile] = useState(false)

  useEffect(() => {
    const close = () => setMenu('')
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])

  const ed = () => getActiveEditor()
  const cmd = (fn: () => void) => {
    if (!canWrite) return
    fn()
  }

  if (hideMenubar) {
    return (
      <div className="note-workspace-bar">
        <button type="button" className="note-menu-restore" onClick={() => onHideMenubar(false)}>
          Menu
        </button>
      </div>
    )
  }

  return (
    <div className="note-workspace-bar">
      <div className="note-chrome">
        <div className={`note-menubar ${mobile ? 'is-mobile-open' : ''}`}>
          <button type="button" className="note-menubar__mobile" onClick={() => setMobile((v) => !v)}>
            Menu
          </button>
          <div className="note-menubar__menus" onClick={(e) => e.stopPropagation()}>
            <div className="note-menu">
              <button
                type="button"
                className="note-menu__btn"
                aria-expanded={menu === 'file'}
                onClick={() => setMenu((m) => (m === 'file' ? '' : 'file'))}
              >
                File
              </button>
              {menu === 'file' ? (
                <div className="note-menu__panel">
                  <button type="button" onClick={() => { setMenu(''); onHistory() }}>History</button>
                  {hasDraft || conflict ? (
                    <button type="button" onClick={() => { setMenu(''); onRecover() }}>Recover draft</button>
                  ) : null}
                  <button type="button" onClick={() => { setMenu(''); onRetry() }}>Retry save</button>
                  {canWrite ? (
                    <button type="button" onClick={() => { setMenu(''); onTrash() }}>Trash page</button>
                  ) : null}
                  <button type="button" onClick={() => { setMenu(''); onSource() }}>HTML source</button>
                  <button type="button" onClick={() => { setMenu(''); onRemind() }}>Remind</button>
                </div>
              ) : null}
            </div>
            <div className="note-menu">
              <button
                type="button"
                className="note-menu__btn"
                aria-expanded={menu === 'view'}
                onClick={() => setMenu((m) => (m === 'view' ? '' : 'view'))}
              >
                View
              </button>
              {menu === 'view' ? (
                <div className="note-menu__panel">
                  <button type="button" onClick={() => { onCompact(!compact); setMenu('') }}>
                    {compact ? 'Roomy tree' : 'Compact tree'}
                  </button>
                  <button type="button" onClick={() => { onHideFmt(!hideFmt); setMenu('') }}>
                    {hideFmt ? 'Show formatting' : 'Hide formatting'}
                  </button>
                  <button type="button" onClick={() => { onHideMenubar(true); setMenu('') }}>
                    Hide menubar
                  </button>
                </div>
              ) : null}
            </div>
            <div className="note-menu">
              <button
                type="button"
                className="note-menu__btn"
                aria-expanded={menu === 'edit'}
                onClick={() => setMenu((m) => (m === 'edit' ? '' : 'edit'))}
              >
                Edit
              </button>
              {menu === 'edit' ? (
                <div className="note-menu__panel">
                  {canWrite ? (
                    <button type="button" onClick={() => { setMenu(''); onMakeTask() }}>
                      Make task from note / selection
                    </button>
                  ) : null}
                  <button type="button" onClick={() => { setMenu(''); onBringTasks() }}>
                    Bring in tasks
                  </button>
                  {canWrite ? (
                    <label className="note-menu__parent">
                      Parent
                      <select value={parentId || ''} onChange={(e) => onParent(Number(e.target.value) || 0)}>
                        <option value="">Top level</option>
                        {pages.filter((p) => p.id !== pageId).map((p) => (
                          <option key={p.id} value={p.id}>{p.title || 'Untitled'}</option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </div>
        <button
          type="button"
          className="note-fmt-toggle"
          title={hideFmt ? 'Show formatting' : 'Hide formatting'}
          aria-label={hideFmt ? 'Show formatting' : 'Hide formatting'}
          onClick={() => onHideFmt(!hideFmt)}
        >
          {hideFmt ? 'Show' : 'Hide'}
        </button>
      </div>
      {!hideFmt && canWrite ? (
        <div className="fmt-bar" role="toolbar" aria-label="Formatting">
          <button type="button" title="Bold" onClick={() => cmd(() => ed()?.chain().focus().toggleBold().run())}><b>B</b></button>
          <button type="button" title="Italic" onClick={() => cmd(() => ed()?.chain().focus().toggleItalic().run())}><i>I</i></button>
          <button type="button" title="Underline" onClick={() => cmd(() => ed()?.chain().focus().toggleUnderline().run())}><u>U</u></button>
          <button type="button" title="Strikethrough" onClick={() => cmd(() => ed()?.chain().focus().toggleStrike().run())}><s>S</s></button>
          <button type="button" className="fmt-ico" title="Undo (Ctrl+Z)" onClick={() => cmd(() => ed()?.chain().focus().undo().run())}>↶</button>
          <button type="button" className="fmt-ico" title="Redo (Ctrl+Y)" onClick={() => cmd(() => ed()?.chain().focus().redo().run())}>↷</button>
          <span className="fmt-bar__sep" />
          <Drop id="listDrop" label="Lists" title="Lists">
            <button type="button" onClick={() => ed()?.chain().focus().toggleBulletList().run()}>• Bullet list</button>
            <button type="button" onClick={() => ed()?.chain().focus().toggleOrderedList().run()}>1. Numbered list</button>
            <button type="button" onClick={() => ed()?.chain().focus().toggleTaskList().run()}>☑ Checklist</button>
          </Drop>
          <button type="button" className="fmt-ico" title="Decrease indent" onClick={() => cmd(() => {
            ed()?.chain().focus().liftListItem('taskItem').run()
            ed()?.chain().focus().liftListItem('listItem').run()
          })}>⇤</button>
          <button type="button" className="fmt-ico" title="Increase indent" onClick={() => cmd(() => {
            ed()?.chain().focus().sinkListItem('taskItem').run()
            ed()?.chain().focus().sinkListItem('listItem').run()
          })}>⇥</button>
          <span className="fmt-bar__sep" />
          <select
            title="Font size"
            defaultValue=""
            onChange={(e) => {
              const n = e.target.value
              if (n) ed()?.chain().focus().setMark('textStyle', { fontSize: `${n}px` }).run()
            }}
          >
            <option value="">Size</option>
            {SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <Drop id="caseDrop" label="Aa" title="Change case of highlighted text">
            <button type="button" onClick={() => applyCase('upper')}>UPPERCASE</button>
            <button type="button" onClick={() => applyCase('lower')}>lowercase</button>
            <button type="button" onClick={() => applyCase('camel')}>camelCase</button>
            <button type="button" onClick={() => applyCase('sentence')}>Sentence case</button>
          </Drop>
          <select
            title="Paragraph style"
            defaultValue="p"
            onChange={(e) => {
              const v = e.target.value
              if (v === 'p') ed()?.chain().focus().setParagraph().run()
              if (v === 'h3') ed()?.chain().focus().toggleHeading({ level: 3 }).run()
              if (v === 'h2') ed()?.chain().focus().toggleHeading({ level: 2 }).run()
              if (v === 'h1') ed()?.chain().focus().toggleHeading({ level: 1 }).run()
            }}
          >
            <option value="p">Normal</option>
            <option value="h3">Heading</option>
            <option value="h2">Large heading</option>
            <option value="h1">Title</option>
          </select>
          <button type="button" className="fmt-ico" title="Align left" onClick={() => cmd(() => ed()?.chain().focus().setTextAlign('left').run())}>≡</button>
          <button type="button" className="fmt-ico" title="Align center" onClick={() => cmd(() => ed()?.chain().focus().setTextAlign('center').run())}>≣</button>
          <button type="button" className="fmt-ico" title="Align right" onClick={() => cmd(() => ed()?.chain().focus().setTextAlign('right').run())}>≡</button>
          <span className="fmt-bar__sep" />
          <Drop id="tableDrop" label="Table" title="Table">
            <button type="button" onClick={() => ed()?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>Insert table…</button>
            <button type="button" onClick={() => ed()?.chain().focus().addRowAfter().run()}>Add row</button>
            <button type="button" onClick={() => ed()?.chain().focus().addColumnAfter().run()}>Add column</button>
            <button type="button" onClick={() => ed()?.chain().focus().deleteRow().run()}>Remove row</button>
            <button type="button" onClick={() => ed()?.chain().focus().deleteColumn().run()}>Remove column</button>
          </Drop>
          <button type="button" title="Horizontal line" onClick={() => cmd(() => ed()?.chain().focus().setHorizontalRule().run())}>—</button>
          <button type="button" title="Link" onClick={() => { setLinkUrl('https://'); setLinkOpen(true) }}>Link</button>
          <label className="fmt-color" title="Image">
            Image
            <input
              hidden
              type="file"
              accept="image/*"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (!file) return
                const body = new FormData()
                body.set('file', file)
                void fetch(`/api/notes/pages/${pageId}/upload`, { method: 'POST', body, credentials: 'same-origin' })
                  .then((r) => r.json())
                  .then((data) => { if (data.url) ed()?.chain().focus().setImage({ src: data.url }).run() })
                e.target.value = ''
              }}
            />
          </label>
          <label className="fmt-color" title="Text color">
            A
            <input type="color" onChange={(e) => ed()?.chain().focus().setColor(e.target.value).run()} />
          </label>
          <Drop id="boxBgDrop" label="Box" title="Box background">
            <div className="fmt-bg__label">Presets</div>
            <div className="fmt-bg__presets">
              {BOX_PRESETS.map((bg) => (
                <button key={bg.label} type="button" className="fmt-bg__preset" style={{ background: bg.id || 'var(--surface)' }} onClick={() => onBoxBg(bg.id)} title={bg.label}>
                  {bg.label[0]}
                </button>
              ))}
            </div>
            <button type="button" onClick={onBoxFront}>Bring to front</button>
            <button type="button" onClick={onBoxBack}>Send to back</button>
            <button type="button" onClick={onBoxDelete}>Delete selected box</button>
            <button type="button" onClick={onBoxRemind}>Remind about this box</button>
          </Drop>
          <span className="fmt-bar__sep" />
          <button type="button" title="HTML source" onClick={onSource}>&lt;/&gt;</button>
          <button type="button" title="Collapse / expand sublist" onClick={() => {
            const cur = ed()?.getAttributes('taskItem')
            ed()?.commands.updateAttributes('taskItem', { collapsed: !cur?.collapsed })
          }}>
            Collapse / expand sublist
          </button>
        </div>
      ) : null}
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
      <p className="sr-only">{pageTitle}</p>
    </div>
  )
}
