import { useMemo, useState, type MouseEvent } from 'react'
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

export const MAP_SKINS = [
  { id: 'inherit', label: 'Match the desk' },
  { id: 'sunshine', label: 'Sunshine' },
  { id: 'ocean', label: 'Ocean' },
  { id: 'candy', label: 'Candy' },
  { id: 'canyon', label: 'Canyon' },
  { id: 'night', label: 'Night neon' },
] as const

export type MapSkin = (typeof MAP_SKINS)[number]['id']

type Place = { id: string; name: string; capital?: string; region?: string }

function readSkin(): MapSkin {
  try {
    const raw = localStorage.getItem('aa.map.skin') || 'inherit'
    return MAP_SKINS.some((s) => s.id === raw) ? (raw as MapSkin) : 'inherit'
  } catch {
    return 'inherit'
  }
}

export function UsaMap({
  places,
  selected,
  highlight,
  status,
  regionTint,
  labels,
  tips,
  onPick,
}: {
  places: Place[]
  selected?: string
  highlight?: string
  status?: Record<string, 'right' | 'wrong' | 'open'>
  regionTint?: boolean
  labels?: boolean
  tips?: boolean
  onPick: (id: string) => void
}) {
  const [box, setBox] = useState(MAP_ZOOMS[0])
  const [focus, setFocus] = useState(highlight || selected || 'TX')
  const [skin, setSkin] = useState<MapSkin>(readSkin)
  const [tip, setTip] = useState<{ x: number; y: number; title: string; sub: string } | null>(null)
  const byId = useMemo(() => Object.fromEntries(places.map((p) => [p.id, p])), [places])
  const ids = useMemo(() => Object.keys(USA_PATHS).filter((id) => byId[id]), [byId])
  const zoomed = box.w < 450
  const view = `${box.x} ${box.y} ${box.w} ${box.h}`

  const moveFocus = (dir: number) => {
    const idx = Math.max(0, ids.indexOf(focus))
    const next = ids[(idx + dir + ids.length) % ids.length]
    setFocus(next)
  }

  const cycleSkin = () => {
    const i = MAP_SKINS.findIndex((s) => s.id === skin)
    const next = MAP_SKINS[(i + 1) % MAP_SKINS.length]
    setSkin(next.id)
    try { localStorage.setItem('aa.map.skin', next.id) } catch { /* ignore */ }
  }

  const showTip = (id: string, ev: MouseEvent) => {
    if (!tips) return
    const place = byId[id]
    if (!place) return
    const host = (ev.currentTarget as SVGPathElement).ownerSVGElement?.parentElement
    const rect = host?.getBoundingClientRect()
    setFocus(id)
    setTip({
      x: ev.clientX - (rect?.left || 0) + 12,
      y: ev.clientY - (rect?.top || 0) + 8,
      title: place.name,
      sub: place.capital || '',
    })
  }

  return (
    <div className="usa-map" data-map-skin={skin}>
      <div className="usa-map__tools" role="toolbar" aria-label="Map zoom and colors">
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
        <button type="button" className="btn btn--small" onClick={cycleSkin}>
          Map colors · {MAP_SKINS.find((s) => s.id === skin)?.label}
        </button>
      </div>
      <div className="usa-map__frame">
        <svg
          className="usa-map__svg"
          viewBox={view || USA_VIEWBOX}
          role="img"
          aria-label="Map of the United States"
          tabIndex={0}
          onMouseLeave={() => setTip(null)}
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
                onMouseEnter={(e) => showTip(id, e)}
                onMouseMove={(e) => showTip(id, e)}
              />
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
        {tip ? (
          <div className="usa-tip" style={{ left: tip.x, top: tip.y }}>
            <strong className="wrap-any">{tip.title}</strong>
            {tip.sub ? <span className="wrap-any">{tip.sub}</span> : null}
          </div>
        ) : null}
      </div>
      <p className="muted usa-map__hint">
        Tap a state. Arrow keys then Enter also work. Zoom in, and cycle map colors if you want a punchier look.
      </p>
    </div>
  )
}
