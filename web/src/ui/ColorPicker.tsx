import { useState, type CSSProperties } from 'react'
import type { ColorOpt } from '../types'

type EyeDropperCtor = new () => { open: () => Promise<{ sRGBHex: string }> }

export function ColorPicker({
  colors,
  value,
  onChange,
}: {
  colors: ColorOpt[]
  value: string
  onChange: (hex: string) => void
}) {
  const [custom, setCustom] = useState(value)
  const canDrop = typeof window !== 'undefined' && 'EyeDropper' in window

  const pick = (hex: string) => {
    setCustom(hex)
    onChange(hex)
  }

  const drop = async () => {
    const Ctor = (window as unknown as { EyeDropper?: EyeDropperCtor }).EyeDropper
    if (!Ctor) return
    try {
      const result = await new Ctor().open()
      pick(result.sRGBHex)
    } catch {
      /* cancelled */
    }
  }

  return (
    <div className="color-picker">
      <div className="color-picks">
        {colors.map((c) => (
          <button
            key={c.hex}
            type="button"
            className="color-swatch"
            onClick={() => pick(c.hex)}
            aria-pressed={value.toLowerCase() === c.hex.toLowerCase()}
          >
            <span className="color-swatch__chip" style={{ '--swatch': c.hex } as CSSProperties} />
            <span>{c.name}</span>
          </button>
        ))}
      </div>
      <div className="color-picker__custom">
        <label className="field">
          <span className="field__label">Any color</span>
          <input
            type="color"
            value={custom.startsWith('#') && (custom.length === 7 || custom.length === 4) ? custom : '#2D6A4F'}
            onChange={(e) => pick(e.target.value)}
          />
        </label>
        {canDrop ? (
          <button type="button" className="btn" onClick={() => void drop()}>
            Eyedropper
          </button>
        ) : null}
      </div>
    </div>
  )
}
