import { Howl } from 'howler'

const clips: Record<string, Howl> = {}

function clip(name: string) {
  if (!clips[name]) {
    clips[name] = new Howl({ src: [`/sounds/${name}.wav`], volume: 0.45 })
  }
  return clips[name]
}

export function playFx(kind: 'correct' | 'miss' | 'star', on: boolean) {
  if (!on) return
  try {
    clip(kind).play()
  } catch {
    /* ignore */
  }
}
