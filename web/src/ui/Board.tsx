import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, ApiError, postJson } from '../api'
import { useAuth } from '../Auth'

export type BoardItem = {
  kind: string
  id: number
  title: string
  subtitle: string
  due: string
  late: boolean
  href: string
  task_id?: number | null
  can_complete?: boolean
}

type BoardData = { today: string; late: BoardItem[]; due: BoardItem[] }

export function Board() {
  const { user } = useAuth()
  const [data, setData] = useState<BoardData | null>(null)
  const [error, setError] = useState('')

  const load = async () => {
    const row = await api<BoardData>('/api/board/today')
    setData(row)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load the board.'))
  }, [])

  if (error) return <div className="status status--error">{error}</div>
  if (!data) return <p className="muted">Loading the board…</p>

  const mark = async (item: BoardItem) => {
    if (!user || !item.task_id) return
    await postJson(`/api/tasks/${item.task_id}/toggle`, { csrf: user.csrf })
    await load()
  }

  const groups = [
    { key: 'late', title: 'Late', items: data.late },
    { key: 'due', title: 'Due today', items: data.due },
  ]

  return (
    <section className="panel board-panel">
      <div className="panel__head">
        <div>
          <p className="eyebrow">Board</p>
          <h2>What is due today</h2>
        </div>
      </div>
      {groups.every((g) => !g.items.length) ? (
        <p className="muted">Nothing is due today. Nice.</p>
      ) : (
        groups.map((group) =>
          group.items.length ? (
            <div key={group.key} className="board-group">
              <h3>{group.title}</h3>
              <div className="board-grid">
                {group.items.map((item) => (
                  <article key={`${item.kind}-${item.id}`} className={`board-card ${item.late ? 'is-late' : ''}`}>
                    <Link to={item.href} className="board-card__link">
                      <p className="eyebrow">{item.late ? 'Late' : item.subtitle}</p>
                      <h3 className="wrap-any">{item.title}</h3>
                      <p className="muted">{item.due}</p>
                    </Link>
                    {item.task_id && item.can_complete && user ? (
                      <button type="button" className="btn btn--small" onClick={() => void mark(item)}>
                        Mark done
                      </button>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null,
        )
      )}
    </section>
  )
}
