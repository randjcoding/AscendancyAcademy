import { DndContext, closestCenter, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Link } from 'react-router-dom'
import { postJson } from '../api'
import { useAuth } from '../Auth'

type Page = { id: number; title: string; parent_id: number | null; sort_order: number }

function Row({ page, currentId }: { page: Page; currentId: number }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: page.id })
  const style = { transform: CSS.Transform.toString(transform), transition }
  return (
    <div ref={setNodeRef} style={style} className="note-tree-node">
      <button type="button" className="btn btn--ghost btn--small" {...attributes} {...listeners}>
        Move
      </button>
      <Link to={`/notes/${page.id}`} className={`tree-item ${currentId === page.id ? 'is-on' : ''}`}>
        <span className="wrap-any">{page.title || 'Untitled'}</span>
      </Link>
    </div>
  )
}

export function SortablePages({
  pages,
  currentId,
  onMoved,
}: {
  pages: Page[]
  currentId: number
  onMoved: () => void
}) {
  const { user } = useAuth()
  const top = pages.filter((p) => !p.parent_id).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)

  const onDragEnd = (event: DragEndEvent) => {
    if (!user || event.active.id === event.over?.id || !event.over) return
    const ids = top.map((p) => p.id)
    const from = ids.indexOf(Number(event.active.id))
    const to = ids.indexOf(Number(event.over.id))
    if (from < 0 || to < 0) return
    const next = [...ids]
    const [moved] = next.splice(from, 1)
    next.splice(to, 0, moved)
    Promise.all(
      next.map((id, i) => postJson(`/api/notes/pages/${id}/reorder`, { csrf: user.csrf, sort_order: i })),
    ).then(onMoved)
  }

  return (
    <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={top.map((p) => p.id)} strategy={verticalListSortingStrategy}>
        {top.map((page) => (
          <Row key={page.id} page={page} currentId={currentId} />
        ))}
      </SortableContext>
    </DndContext>
  )
}
