import { useMemo, useState } from 'react'

type NamedPlace = { name: string; capital: string }

function norm(value: string): string {
  return value.toLowerCase().replace(/[^a-z]/g, '')
}

export function wordList(places: NamedPlace[]): { states: string[]; capitals: string[]; all: string[] } {
  const states = [...new Set(places.map((p) => p.name))].sort((a, b) => a.localeCompare(b))
  const capitals = [...new Set(places.map((p) => p.capital))].sort((a, b) => a.localeCompare(b))
  return { states, capitals, all: [...states, ...capitals] }
}

export function typedMatch(typed: string, answer: string): boolean {
  const a = norm(typed)
  const b = norm(answer)
  if (!a || a !== b) {
    if (b.startsWith('saint') && a === `st${b.slice(5)}`) return true
    if (b.startsWith('st') && a === `saint${b.slice(2)}`) return true
    return false
  }
  return true
}

function distance(a: string, b: string): number {
  const rows = a.length + 1
  const cols = b.length + 1
  const dp: number[] = new Array(rows * cols)
  for (let i = 0; i < rows; i += 1) dp[i * cols] = i
  for (let j = 0; j < cols; j += 1) dp[j] = j
  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      dp[i * cols + j] = Math.min(
        dp[(i - 1) * cols + j] + 1,
        dp[i * cols + j - 1] + 1,
        dp[(i - 1) * cols + (j - 1)] + cost,
      )
    }
  }
  return dp[(rows - 1) * cols + (cols - 1)]
}

export function spellingMatch(typed: string, answer: string, helpOn: boolean): boolean {
  if (typedMatch(typed, answer)) return true
  if (!helpOn) return false
  const a = norm(typed)
  const b = norm(answer)
  if (a.length < 3) return false
  const allow = b.length <= 5 ? 1 : b.length <= 9 ? 2 : 3
  if (Math.abs(a.length - b.length) > allow) return false
  return distance(a, b) <= allow
}

export function suggestWords(typed: string, words: string[]): string[] {
  const n = norm(typed)
  if (n.length < 1) return []
  return words
    .filter((w) => {
      const wn = norm(w)
      return wn.startsWith(n) || (n.length >= 2 && wn.includes(n))
    })
    .slice(0, 8)
}

export function WordBook({
  places,
  typed,
  onPick,
}: {
  places: NamedPlace[]
  typed: string
  onPick: (word: string) => void
}) {
  const [open, setOpen] = useState(false)
  const book = useMemo(() => wordList(places), [places])
  const hints = useMemo(() => suggestWords(typed, book.all), [typed, book.all])

  return (
    <div className="word-book">
      {hints.length ? (
        <div className="word-book__hints" role="listbox" aria-label="Spelling suggestions">
          {hints.map((word) => (
            <button key={word} type="button" className="btn" onClick={() => onPick(word)}>
              {word}
            </button>
          ))}
        </div>
      ) : null}
      <button type="button" className="linkish" onClick={() => setOpen((v) => !v)}>
        {open ? 'Hide word book' : 'Open word book'}
      </button>
      {open ? (
        <div className="word-book__list">
          <div className="word-book__col">
            <p className="field__label">States</p>
            {book.states.map((word) => (
              <button key={word} type="button" className="word-book__word" onClick={() => onPick(word)}>
                {word}
              </button>
            ))}
          </div>
          <div className="word-book__col">
            <p className="field__label">Capitals</p>
            {book.capitals.map((word) => (
              <button key={word} type="button" className="word-book__word" onClick={() => onPick(word)}>
                {word}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
