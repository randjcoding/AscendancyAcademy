import confetti from 'canvas-confetti'
import { useEffect } from 'react'

export function celebrate(stars: number, perfect: boolean) {
  const gold = getComputedStyle(document.documentElement).getPropertyValue('--gold').trim() || '#d4b44a'
  const brand = getComputedStyle(document.documentElement).getPropertyValue('--brand').trim() || '#2d6a4f'
  if (stars >= 3 || perfect) {
    void confetti({ particleCount: 140, spread: 80, origin: { y: 0.55 }, colors: [gold, brand, '#fffaf0'] })
  } else if (stars >= 2) {
    void confetti({ particleCount: 70, spread: 55, origin: { y: 0.6 }, colors: [gold, brand] })
  }
}

export function StarBurst({ stars }: { stars: number }) {
  useEffect(() => {
    if (stars >= 2) celebrate(stars, stars >= 3)
  }, [stars])
  return null
}
