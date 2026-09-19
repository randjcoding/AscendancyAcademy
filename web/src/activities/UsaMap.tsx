import { useEffect, useMemo, useRef, useState, type PointerEvent, type TouchEvent } from 'react'
import { USA_CENTROIDS } from './maps/usaCentroids'
import { USA_PATHS, USA_VIEWBOX } from './maps/usaPaths'

const REGIONS: Record<string, string> = {
  Northeast: 'region-ne',
  South: 'region-so',
  Midwest: 'region-mw',
  West: 'region-we',
}

export type MapBox = { id: string; label: string; x: number; y: number; w: number; h: number }

const WORLD = { x: 0, y: 0, w: 1000, h: 589 }
const MIN_W = 70
const WORLD_ASPECT = WORLD.h / WORLD.w

export const MAP_ZOOMS: MapBox[] = [
  { id: 'whole', label: 'Whole map', x: 0, y: 0, w: 1000, h: 589 },
  { id: 'new_england', label: 'New England', x: 820, y: 8, w: 190, h: 210 },
  { id: 'mid_atlantic', label: 'Mid-Atlantic', x: 760, y: 55, w: 230, h: 250 },
  { id: 'south', label: 'South', x: 460, y: 220, w: 430, h: 350 },
  { id: 'midwest', label: 'Midwest', x: 480, y: 40, w: 320, h: 310 },
  { id: 'mountain_west', label: 'Mountain West', x: 200, y: 30, w: 340, h: 430 },
  { id: 'pacific', label: 'Pacific', x: 0, y: 0, w: 460, h: 589 },
]

export function boxForState(id: string): MapBox {
  if (id === 'AK') return { id: 'AK', label: 'Alaska', x: 0, y: 420, w: 280, h: 170 }
  if (id === 'HI') return { id: 'HI', label: 'Hawaii', x: 300, y: 470, w: 160, h: 120 }
  const pt = USA_CENTROIDS[id]
  if (!pt) return MAP_ZOOMS[0]
  const pad = id === 'TX' || id === 'CA' || id === 'MT' ? 110 : 72
  return {
    id,
    label: id,
    x: Math.max(0, pt.x - pad),
    y: Math.max(0, pt.y - pad),
    w: pad * 2,
    h: pad * 2,
  }
}

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
type Cam = { x: number; y: number; w: number; h: number }

function readSkin(): MapSkin {
  try {
    const raw = localStorage.getItem('aa.map.skin') || 'inherit'
    return MAP_SKINS.some((s) => s.id === raw) ? (raw as MapSkin) : 'inherit'
  } catch {
    return 'inherit'
  }
}

function clampCam(cam: Cam, aspect: number): Cam {
  let w = Math.min(WORLD.w, Math.max(MIN_W, cam.w))
  let h = w * aspect
  if (h > WORLD.h) {
    h = WORLD.h
    w = Math.min(WORLD.w, h / aspect)
  }
  const x = Math.min(WORLD.w - w, Math.max(WORLD.x, cam.x))
  const y = Math.min(WORLD.h - h, Math.max(WORLD.y, cam.y))
  return { x, y, w, h }
}

function fitBox(target: MapBox, aspect: number): Cam {
  const pad = 12
  const tw = target.w + pad * 2
  const th = target.h + pad * 2
  const ta = th / tw
  let w = tw
  let h = th
  if (ta < aspect) h = w * aspect
  else w = h / aspect
  return clampCam(
    {
      x: target.x + target.w / 2 - w / 2,
      y: target.y + target.h / 2 - h / 2,
      w,
      h,
    },
    aspect,
  )
}

function zoomToward(cam: Cam, factor: number, sx: number, sy: number, aspect: number): Cam {
  const next = clampCam({ ...cam, w: cam.w * factor, h: cam.h * factor }, aspect)
  const kx = (sx - cam.x) / cam.w
  const ky = (sy - cam.y) / cam.h
  return clampCam({ ...next, x: sx - kx * next.w, y: sy - ky * next.h }, aspect)
}

function touchDist(a: { clientX: number; clientY: number }, b: { clientX: number; clientY: number }) {
  return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY)
}

export function UsaMap({
  places,
  selected,
  highlight,
  status,
  regionTint,
  labels,
  tips,
  zoomId,
  onPick,
  onZoom,
}: {
  places: Place[]
  selected?: string
  highlight?: string
  status?: Record<string, 'right' | 'wrong' | 'open'>
  regionTint?: boolean
  labels?: boolean
  tips?: boolean
  zoomId?: string
  onPick: (id: string) => void
  onZoom?: (id: string) => void
}) {
  const frameRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const camRef = useRef<Cam>(MAP_ZOOMS[0])
  const aspectRef = useRef(WORLD_ASPECT)
  const dragRef = useRef<{ x: number; y: number; camX: number; camY: number; moved: boolean } | null>(null)
  const pinchRef = useRef<{ dist: number; sx: number; sy: number; cam: Cam } | null>(null)
  const skipPick = useRef(false)
  const [aspect, setAspect] = useState(WORLD_ASPECT)
  const [cam, setCam] = useState(() => fitBox(MAP_ZOOMS.find((z) => z.id === zoomId) || MAP_ZOOMS[0], WORLD_ASPECT))
  const [skin, setSkin] = useState<MapSkin>(readSkin)
  const [dragging, setDragging] = useState(false)
  const [frameW, setFrameW] = useState(800)
  const [tip, setTip] = useState<{ x: number; y: number; title: string; sub: string } | null>(null)
  const byId = useMemo(() => Object.fromEntries(places.map((p) => [p.id, p])), [places])
  const ids = useMemo(() => Object.keys(USA_PATHS).filter((id) => byId[id]), [byId])
  const view = `${cam.x} ${cam.y} ${cam.w} ${cam.h}`
  const quietSize = Math.max(5.5, 11 * (cam.w / Math.max(frameW, 1)))
  const loudSize = Math.max(8, 17 * (cam.w / Math.max(frameW, 1)))

  camRef.current = cam
  aspectRef.current = aspect

  useEffect(() => {
    const el = frameRef.current
    if (!el) return
    const sync = () => {
      const r = el.getBoundingClientRect()
      if (r.width > 8 && r.height > 8) {
        setFrameW(r.width)
        setAspect(r.height / r.width)
      }
    }
    sync()
    const ro = new ResizeObserver(sync)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    setCam((c) => clampCam({ ...c, h: c.w * aspect }, aspect))
  }, [aspect])

  useEffect(() => {
    const next = MAP_ZOOMS.find((z) => z.id === zoomId)
    if (next) setCam(fitBox(next, aspectRef.current))
  }, [zoomId])

  useEffect(() => {
    const node = frameRef.current
    if (!node) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const svg = svgRef.current
      if (!svg) return
      const rect = svg.getBoundingClientRect()
      const cur = camRef.current
      const sx = cur.x + ((e.clientX - rect.left) / rect.width) * cur.w
      const sy = cur.y + ((e.clientY - rect.top) / rect.height) * cur.h
      const step = e.ctrlKey ? 0.012 : 0.0022
      const factor = Math.min(1.25, Math.max(0.8, Math.exp(e.deltaY * step)))
      setCam(zoomToward(cur, factor, sx, sy, aspectRef.current))
    }
    node.addEventListener('wheel', onWheel, { passive: false })
    return () => node.removeEventListener('wheel', onWheel)
  }, [])

  const toSvg = (clientX: number, clientY: number) => {
    const svg = svgRef.current
    const cur = camRef.current
    if (!svg) return { x: cur.x + cur.w / 2, y: cur.y + cur.h / 2 }
    const rect = svg.getBoundingClientRect()
    return {
      x: cur.x + ((clientX - rect.left) / rect.width) * cur.w,
      y: cur.y + ((clientY - rect.top) / rect.height) * cur.h,
    }
  }

  const applyCam = (next: Cam) => setCam(clampCam(next, aspectRef.current))

  const lookAt = (box: MapBox) => applyCam(fitBox(box, aspectRef.current))

  const goBox = (box: MapBox) => {
    lookAt(box)
    onZoom?.(box.id)
  }

  const zoomCenter = (factor: number) => {
    const cur = camRef.current
    applyCam(zoomToward(cur, factor, cur.x + cur.w / 2, cur.y + cur.h / 2, aspectRef.current))
  }

  const panBy = (dx: number, dy: number) => {
    const cur = camRef.current
    applyCam({ ...cur, x: cur.x + dx * cur.w, y: cur.y + dy * cur.h })
  }

  const cycleSkin = () => {
    const i = MAP_SKINS.findIndex((s) => s.id === skin)
    const next = MAP_SKINS[(i + 1) % MAP_SKINS.length]
    setSkin(next.id)
    try {
      localStorage.setItem('aa.map.skin', next.id)
    } catch {
      /* ignore */
    }
  }

  const showTip = (id: string, clientX: number, clientY: number) => {
    if (!tips) return
    const place = byId[id]
    const host = frameRef.current
    if (!place || !host) return
    const rect = host.getBoundingClientRect()
    setTip({
      x: clientX - rect.left + 12,
      y: clientY - rect.top + 8,
      title: place.name,
      sub: place.capital || '',
    })
  }

  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => {
    if (e.pointerType === 'touch' && pinchRef.current) return
    ;(e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId)
    dragRef.current = { x: e.clientX, y: e.clientY, camX: cam.x, camY: cam.y, moved: false }
    setDragging(true)
  }

  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current
    if (!drag || pinchRef.current) return
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    const dx = ((e.clientX - drag.x) / rect.width) * camRef.current.w
    const dy = ((e.clientY - drag.y) / rect.height) * camRef.current.h
    if (Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y) > 7) drag.moved = true
    applyCam({ ...camRef.current, x: drag.camX - dx, y: drag.camY - dy })
  }

  const onPointerUp = (e: PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current
    dragRef.current = null
    setDragging(false)
    if (skipPick.current) {
      skipPick.current = false
      return
    }
    if (!drag || drag.moved || pinchRef.current) return
    const node = document.elementFromPoint(e.clientX, e.clientY)
    const id = node instanceof SVGPathElement ? node.id : ''
    if (id && byId[id]) onPick(id)
  }

  const onTouchStart = (e: TouchEvent<SVGSVGElement>) => {
    if (e.touches.length < 2) return
    e.preventDefault()
    const a = e.touches[0]
    const b = e.touches[1]
    const mid = toSvg((a.clientX + b.clientX) / 2, (a.clientY + b.clientY) / 2)
    pinchRef.current = { dist: touchDist(a, b), sx: mid.x, sy: mid.y, cam: { ...camRef.current } }
    skipPick.current = true
    dragRef.current = null
  }

  const onTouchMove = (e: TouchEvent<SVGSVGElement>) => {
    if (e.touches.length < 2 || !pinchRef.current) return
    e.preventDefault()
    const a = e.touches[0]
    const b = e.touches[1]
    const pinch = pinchRef.current
    const dist = touchDist(a, b)
    if (pinch.dist < 8 || dist < 8) return
    const mid = toSvg((a.clientX + b.clientX) / 2, (a.clientY + b.clientY) / 2)
    applyCam(zoomToward(camRef.current, pinch.dist / dist, mid.x, mid.y, aspectRef.current))
    pinch.dist = dist
  }

  const onTouchEnd = (e: TouchEvent<SVGSVGElement>) => {
    if (e.touches.length < 2) pinchRef.current = null
  }

  return (
    <div className="usa-map" data-map-skin={skin}>
      <div className="usa-map__tools" role="toolbar" aria-label="Map regions and colors">
        {MAP_ZOOMS.map((z) => (
          <button
            key={z.id}
            type="button"
            className={`btn btn--small ${(zoomId || 'whole') === z.id ? 'btn--primary' : 'btn--ghost'}`}
            onClick={() => goBox(z)}
          >
            {z.label}
          </button>
        ))}
        <button type="button" className="btn btn--small" onClick={cycleSkin}>
          Map colors · {MAP_SKINS.find((s) => s.id === skin)?.label}
        </button>
      </div>
      <div
        className="usa-map__frame"
        ref={frameRef}
        onMouseLeave={() => setTip(null)}
      >
        <svg
          ref={svgRef}
          className={`usa-map__svg ${dragging ? 'is-drag' : ''}`}
          viewBox={view || USA_VIEWBOX}
          role="img"
          aria-label="Map of the United States"
          tabIndex={0}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={() => {
            dragRef.current = null
            setDragging(false)
          }}
          onTouchStart={onTouchStart}
          onTouchMove={onTouchMove}
          onTouchEnd={onTouchEnd}
          onKeyDown={(e) => {
            if (e.key === 'ArrowRight') {
              e.preventDefault()
              panBy(0.16, 0)
            }
            if (e.key === 'ArrowLeft') {
              e.preventDefault()
              panBy(-0.16, 0)
            }
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              panBy(0, 0.16)
            }
            if (e.key === 'ArrowUp') {
              e.preventDefault()
              panBy(0, -0.16)
            }
            if (e.key === '+' || e.key === '=') {
              e.preventDefault()
              zoomCenter(0.82)
            }
            if (e.key === '-' || e.key === '_') {
              e.preventDefault()
              zoomCenter(1.22)
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
              selected === id || highlight === id ? 'is-focus' : '',
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
                onPointerEnter={(e) => showTip(id, e.clientX, e.clientY)}
                onPointerMove={(e) => showTip(id, e.clientX, e.clientY)}
              />
            )
          })}
          {labels
            ? ids.map((id) => {
                const place = byId[id]
                const pt = USA_CENTROIDS[id]
                if (!place || !pt) return null
                const loud = selected === id
                const size = loud ? loudSize : quietSize
                return (
                  <text
                    key={`label-${id}`}
                    className={`usa-label ${loud ? 'is-loud' : ''}`}
                    x={pt.x}
                    y={pt.y}
                    fontSize={size}
                    strokeWidth={loud ? size * 0.22 : size * 0.28}
                    pointerEvents="none"
                  >
                    <tspan x={pt.x} dy={loud ? '-0.45em' : '0.35em'}>
                      {loud ? place.name : id}
                    </tspan>
                    {loud && place.capital ? (
                      <tspan x={pt.x} dy="1.25em">
                        {place.capital}
                      </tspan>
                    ) : null}
                  </text>
                )
              })
            : null}
        </svg>
        <div className="usa-map__zoom">
          <button type="button" className="btn btn--small" onClick={() => zoomCenter(0.8)}>
            Closer
          </button>
          <button type="button" className="btn btn--small" onClick={() => zoomCenter(1.25)}>
            Farther
          </button>
          <button type="button" className="btn btn--small" onClick={() => lookAt(MAP_ZOOMS[0])}>
            Whole map
          </button>
        </div>
        {tip ? (
          <div className="usa-tip" style={{ left: tip.x, top: tip.y }}>
            <strong className="wrap-any">{tip.title}</strong>
            {tip.sub ? <span className="wrap-any">{tip.sub}</span> : null}
          </div>
        ) : null}
      </div>
      <p className="muted usa-map__hint">
        Scroll or pinch to zoom. Drag or use the arrow keys to move. Only the state you tap gets the big name.
      </p>
    </div>
  )
}
