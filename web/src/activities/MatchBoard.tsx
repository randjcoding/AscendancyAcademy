import { useMemo, useState } from 'react'

export type MatchPlace = { id: string; name: string; capital: string }

export function MatchBoard({
  places,
  done,
  onScore,
  onItem,
}: {
  places: MatchPlace[]
  done: boolean
  onScore: (right: number, total: number, finished: boolean) => void
  onItem?: (id: string, correct: boolean) => void
}) {
  const capitals = useMemo(() => {
    const copy = places.map((p) => ({ id: p.id, text: p.capital }))
    for (let i = copy.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[copy[i], copy[j]] = [copy[j], copy[i]]
    }
    return copy
  }, [places])

  const [matched, setMatched] = useState<Record<string, 'right' | 'wrong'>>({})
  const [holding, setHolding] = useState<{ id: string; kind: 'state' | 'capital' } | null>(null)
  const [used, setUsed] = useState<Set<string>>(new Set())

  const tryPair = (stateId: string, capitalId: string) => {
    if (done || used.has(stateId) || used.has(`c-${capitalId}`)) return
    const ok = stateId === capitalId
    onItem?.(stateId, ok)
    setMatched((m) => ({ ...m, [stateId]: ok ? 'right' : 'wrong' }))
    if (ok) {
      const next = new Set(used)
      next.add(stateId)
      next.add(`c-${capitalId}`)
      setUsed(next)
      const right = Object.values({ ...matched, [stateId]: 'right' }).filter((v) => v === 'right').length
      onScore(right, places.length, next.size / 2 >= places.length)
    } else {
      const right = Object.values(matched).filter((v) => v === 'right').length
      onScore(right, places.length, false)
      window.setTimeout(() => {
        setMatched((m) => {
          const copy = { ...m }
          if (copy[stateId] === 'wrong') delete copy[stateId]
          return copy
        })
      }, 700)
    }
    setHolding(null)
  }

  const onDrop = (targetId: string, targetKind: 'state' | 'capital') => {
    if (!holding || holding.kind === targetKind) return
    const stateId = holding.kind === 'state' ? holding.id : targetId
    const capitalId = holding.kind === 'capital' ? holding.id : targetId
    tryPair(stateId, capitalId)
  }

  return (
    <div className="match-board">
      <p className="muted">
        Drag a capital onto its state, or a state onto its capital. You can also click one, then the other.
      </p>
      <div className="match-cols">
        <div>
          <h3>States</h3>
          <ul className="match-list">
            {places.map((p) => {
              const mark = matched[p.id]
              const taken = used.has(p.id)
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    draggable={!taken && !done}
                    className={`match-chip ${mark === 'right' ? 'is-right' : ''} ${mark === 'wrong' ? 'is-wrong' : ''} ${holding?.id === p.id && holding.kind === 'state' ? 'is-hold' : ''}`}
                    disabled={taken || done}
                    onDragStart={() => setHolding({ id: p.id, kind: 'state' })}
                    onDragEnd={() => setHolding(null)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault()
                      onDrop(p.id, 'state')
                    }}
                    onClick={() => {
                      if (holding?.kind === 'capital') onDrop(p.id, 'state')
                      else setHolding({ id: p.id, kind: 'state' })
                    }}
                  >
                    <span className="wrap-any">{p.name}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
        <div>
          <h3>Capitals</h3>
          <ul className="match-list">
            {capitals.map((c) => {
              const taken = used.has(`c-${c.id}`)
              const mark = matched[c.id]
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    draggable={!taken && !done}
                    className={`match-chip ${taken ? 'is-right' : ''} ${mark === 'wrong' && holding?.id === c.id ? 'is-wrong' : ''} ${holding?.id === c.id && holding.kind === 'capital' ? 'is-hold' : ''}`}
                    disabled={taken || done}
                    onDragStart={() => setHolding({ id: c.id, kind: 'capital' })}
                    onDragEnd={() => setHolding(null)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault()
                      onDrop(c.id, 'capital')
                    }}
                    onClick={() => {
                      if (holding?.kind === 'state') onDrop(c.id, 'capital')
                      else setHolding({ id: c.id, kind: 'capital' })
                    }}
                  >
                    <span className="wrap-any">{c.text}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}
