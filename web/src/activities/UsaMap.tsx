import { useMemo, useState } from 'react'
import { USA_CENTROIDS } from './maps/usaCentroids'
import { USA_PATHS, USA_VIEWBOX } from './maps/usaPaths'

const REGIONS: Record<string, string> = {
  Northeast: 'region-ne',
  South: 'region-so',
  Midwest: 'region-mw',
  West: 'region-we',
}

export type MapBox = { id: string; label: string; x: number; y: number; w: number; h: number }

export const MAP_ZOOMS: MapBox[] = [
  { id: 'whole', label: 'Whole map', x: 0, y: 0, w: 1000, h: 589 },
  { id: 'west', label: 'West', x: 0, y: 20, w: 420, h: 400 },
  { id: 'midwest', label: 'Midwest', x: 500, y: 60, w: 280, h: 280 },
  { id: 'south', label: 'South', x: 480, y: 240, w: 400, h: 330 },
  { id: 'northeast', label: 'Northeast', x: 780, y: 50, w: 230, h: 240 },
  { id: 'new_england', label: 'New England', x: 860, y: 40, w: 150, h: 180 },
  { id: 'alaska', label: 'Alaska', x: 0, y: 420, w: 280, h: 170 },
  { id: 'hawaii', label: 'Hawaii', x: 300, y: 470, w: 160, h: 120 },
]

type Place = { id: string; name: string; capital?: string; region?: string }

export function UsaMap({
  places,
  selected,
  highlight,
  status,
  regionTint,
  labels,
  onPick,
}: {
  places: Place[]
  selected?: string
  highlight?: string
  status?: Record<string, 'right' | 'wrong' | 'open'>
  regionTint?: boolean
  labels?: boolean
  onPick: (id: string) => void
}) {
  const [box, setBox] = useState(MAP_ZOOMS[0])
  const [focus, setFocus] = useState(highlight || selected || 'TX')
  const byId = useMemo(() => Object.fromEntries(places.map((p) => [p.id, p])), [places])
  const ids = useMemo(() => Object.keys(USA_PATHS).filter((id) => byId[id]), [byId])
  const zoomed = box.w < 450
  const view = `${box.x} ${box.y} ${box.w} ${box.h}`

  const moveFocus = (dir: number) => {
    const idx = Math.max(0, ids.indexOf(focus))
    const next = ids[(idx + dir + ids.length) % ids.length]
    setFocus(next)
  }

  return (
    <div className="usa-map">
      <div className="usa-map__tools" role="toolbar" aria-label="Map zoom">
        {MAP_ZOOMS.map((z) => (
          <button
            key={z.id}
            type="button"
            className={`btn btn--small ${box.id === z.id ? 'btn--primary' : 'btn--ghost'}`}
            onClick={() => setBox(z)}
          >
            {z.label}
          </button>
        ))}
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
              <title>{place.capital ? `${place.name} — ${place.capital}` : place.name}</title>
            </path>
          )
        })}
        {labels
          ? ids.map((id) => {
              const place = byId[id]
              const pt = USA_CENTROIDS[id]
              if (!place || !pt) return null
              const title = zoomed ? place.name : id
              const cap = place.capital || ''
              return (
                <text
                  key={`label-${id}`}
                  className={`usa-label ${zoomed ? 'is-zoom' : ''}`}
                  x={pt.x}
                  y={pt.y}
                  pointerEvents="none"
                >
                  <tspan x={pt.x} dy="-0.35em">
                    {title}
                  </tspan>
                  {cap ? (
                    <tspan x={pt.x} dy="1.25em">
                      {cap}
                    </tspan>
                  ) : null}
                </text>
              )
            })
          : null}
      </svg>
      <p className="muted usa-map__hint">
        Tap a state. Arrow keys then Enter also work. Use the zoom buttons to get closer to tiny states.
      </p>
    </div>
  )
}
