import { useEffect, useRef } from 'react'

const MARK_SRC = '/mark.png'

function paint(canvas: HTMLCanvasElement, image: HTMLImageElement) {
  const css = getComputedStyle(canvas)
  const box = canvas.getBoundingClientRect()
  const width = Math.max(1, Math.round(box.width))
  const height = Math.max(1, Math.round(box.height))
  if (!width || !height || !image.naturalWidth) return
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.round(width * dpr)
  canvas.height = Math.round(height * dpr)
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(image, 0, 0, canvas.width, canvas.height)
  ctx.globalCompositeOperation = 'source-in'
  ctx.fillStyle = css.color || '#111'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.globalCompositeOperation = 'source-over'
}

export function BrandMark() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const image = new Image()
    image.decoding = 'async'
    let alive = true

    const redraw = () => {
      if (alive && image.complete && image.naturalWidth) paint(canvas, image)
    }

    image.onload = redraw
    image.src = MARK_SRC
    if (image.complete) redraw()

    const themeWatch = new MutationObserver(redraw)
    themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    const sizeWatch = new ResizeObserver(redraw)
    sizeWatch.observe(canvas)

    return () => {
      alive = false
      themeWatch.disconnect()
      sizeWatch.disconnect()
    }
  }, [])

  return <canvas className="brand__mon" aria-hidden="true" ref={ref} />
}
