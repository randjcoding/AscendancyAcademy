import { useEffect, useState } from 'react'

const MARK_SRC = '/mark.png'

function inkRgb(color: string): [number, number, number] {
  const m = color.match(/rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i)
  if (!m) return [17, 17, 17]
  return [Number(m[1]), Number(m[2]), Number(m[3])]
}

function tintMark(image: HTMLImageElement, color: string): string {
  const canvas = document.createElement('canvas')
  canvas.width = image.naturalWidth
  canvas.height = image.naturalHeight
  const ctx = canvas.getContext('2d')
  if (!ctx) return MARK_SRC
  ctx.drawImage(image, 0, 0)
  const frame = ctx.getImageData(0, 0, canvas.width, canvas.height)
  const [r, g, b] = inkRgb(color)
  const pix = frame.data
  for (let i = 0; i < pix.length; i += 4) {
    if (pix[i + 3] === 0) continue
    pix[i] = r
    pix[i + 1] = g
    pix[i + 2] = b
  }
  ctx.putImageData(frame, 0, 0)
  return canvas.toDataURL('image/png')
}

export function BrandMark() {
  const [src, setSrc] = useState('')

  useEffect(() => {
    const probe = document.createElement('span')
    probe.className = 'brand__mon'
    probe.style.position = 'absolute'
    probe.style.visibility = 'hidden'
    document.body.appendChild(probe)

    const image = new Image()
    let alive = true

    const paint = () => {
      if (!alive || !image.naturalWidth) return
      const color = getComputedStyle(probe).color || getComputedStyle(document.body).color
      setSrc(tintMark(image, color))
    }

    image.onload = paint
    image.src = MARK_SRC
    if (image.complete) paint()

    const watch = new MutationObserver(paint)
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

    return () => {
      alive = false
      watch.disconnect()
      probe.remove()
    }
  }, [])

  if (!src) return <span className="brand__mon" aria-hidden="true" />

  return <img className="brand__mon" src={src} alt="" draggable={false} />
}
