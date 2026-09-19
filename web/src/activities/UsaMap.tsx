import { useMemo, useState } from 'react'
import { USA_PATHS, USA_VIEWBOX } from './maps/usaPaths'

const REGIONS: Record<string, string> = {
  Northeast: 'region-ne',
  South: 'region-so',
  Midwest: 'region-mw',
  West: 'region-we',
}

const NE_BOX = { x: 780, y: 70, w: 230, h: 230 }
const FULL = { x: 0, y: 0, w: 1000, h: 589 }

type Place = { id: string; name: string; region?: string }

export function UsaMap({
  places,
  selected,
  highlight,
  status,
  regionTint,
  onPick,
}: {
  places: Place[]
  selected?: string
  highlight?: string
  status?: Record<string, 'right' | 'wrong' | 'open'>
  regionTint?: boolean
  onPick: (id: string) => void
}) {
  const [box, setBox] = useState(FULL)
  const [focus, setFocus] = useState(highlight || selected || 'TX')
  const byId = useMemo(() => Object.fromEntries(places.map((p) => [p.id, p])), [places])
  const ids = useMemo(() => Object.keys(USA_PATHS).filter((id) => byId[id]), [byId])

  const view = `${box.x} ${box.y} ${box.w} ${box.h}`

  const moveFocus = (dir: number) => {
    const idx = Math.max(0, ids.indexOf(focus))
    const next = ids[(idx + dir + ids.length) % ids.length]
    setFocus(next)
  }

  return (
    <div className="usa-map">
      <div className="usa-map__tools">
        <button type="button" className="btn btn--small" onClick={() => setBox(box === FULL ? NE_BOX : FULL)}>
          {box === FULL ? 'Zoom Northeast' : 'See whole map'}
        </button>
        <button type="button" className="btn btn--small btn--ghost" onClick={() => setBox(FULL)}>Reset</button>
      </div>
      <svg
        className="usa-map__svg"
        viewBox={view || USA_VIEWBOX}
        role="img"
        aria-label="Map of the United States"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault()
            moveFocus(1)
          }
          if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault()
            moveFocus(-1)
          }
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onPick(focus)
          }
        }}
      >
        {Object.entries(USA_PATHS).map(([id, d]) => {
          const place = byId[id]
          if (!place) return null
          const mark = status?.[id]
          const classes = [
            'usa-state',
            regionTint && place.region ? REGIONS[place.region] : '',
            selected === id || focus === id ? 'is-focus' : '',
            highlight === id ? 'is-lit' : '',
            mark === 'right' ? 'is-right' : '',
            mark === 'wrong' ? 'is-wrong' : '',
          ]
            .filter(Boolean)
            .join(' ')
          return (
            <path
              key={id}
              id={id}
              d={d}
              className={classes}
              onClick={() => {
                setFocus(id)
                onPick(id)
              }}
              onMouseEnter={() => setFocus(id)}
            >
              <title>{place.name}</title>
            </path>
          )
        })}
      </svg>
      <p className="muted usa-map__hint">Tap a state. Arrow keys then Enter also work. Zoom Northeast if Rhode Island is tiny.</p>
    </div>
  )
}
