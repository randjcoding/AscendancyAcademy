import { useEffect, useMemo, useState } from 'react'
import { postJson } from '../api'
import { DrillHud, Stars } from './DrillHud'
import { playFx } from './sound'
import { StarBurst } from './StarBurst'
import { UsaMap } from './UsaMap'

export type Place = {
  id: string
  name: string
  capital: string
  capital_phonetic: string
  tip: string
  region: string
}

export type ActivityPayload = {
  activity_id: string
  title: string
  modes: string[]
  content: Place[]
  best_stars?: number
}

type Mode = 'study' | 'find_on_map' | 'name_the_capital' | 'flashcards'

const MODE_LABEL: Record<Mode, string> = {
  study: 'Study the map',
  find_on_map: 'Find the state',
  name_the_capital: 'Name the capital',
  flashcards: 'Speed round',
}

function shuffle<T>(items: T[]): T[] {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy
}

function choicesFor(place: Place, all: Place[]): string[] {
  const same = all.filter((p) => p.id !== place.id && p.region === place.region)
  const rest = all.filter((p) => p.id !== place.id && p.region !== place.region)
  const pool = shuffle([...same, ...rest]).slice(0, 3).map((p) => p.capital)
  return shuffle([place.capital, ...pool])
}

export function ActivityRunner({
  activity,
  csrf,
  soundOn,
}: {
  activity: ActivityPayload
  csrf: string
  soundOn: boolean
}) {
  const [mode, setMode] = useState<Mode | ''>('')
  if (!mode) {
    return (
      <section className="panel">
        <h2>Pick a way to play</h2>
        <div className="mode-grid">
          {(Object.keys(MODE_LABEL) as Mode[]).map((m) => (
            <button key={m} type="button" className="mode-card" onClick={() => setMode(m)}>
              <strong>{MODE_LABEL[m]}</strong>
              <span className="muted">
                {m === 'study' && 'Hover and tap. Learn the capital, how to say it, and a memory tip.'}
                {m === 'find_on_map' && 'We name a capital. You tap the state.'}
                {m === 'name_the_capital' && 'We light up a state. You pick its capital.'}
                {m === 'flashcards' && 'Sixty seconds. How many can you name?'}
              </span>
            </button>
          ))}
        </div>
      </section>
    )
  }
  return <Drill key={mode} mode={mode} activity={activity} csrf={csrf} soundOn={soundOn} onExit={() => setMode('')} />
}

function Drill({
  mode,
  activity,
  csrf,
  soundOn,
  onExit,
}: {
  mode: Mode
  activity: ActivityPayload
  csrf: string
  soundOn: boolean
  onExit: () => void
}) {
  const places = activity.content
  const deck = useMemo(() => shuffle(places), [places, mode])
  const [i, setI] = useState(0)
  const [score, setScore] = useState(0)
  const [streak, setStreak] = useState(0)
  const [misses, setMisses] = useState(0)
  const [tries, setTries] = useState(0)
  const [status, setStatus] = useState<Record<string, 'right' | 'wrong' | 'open'>>({})
  const [picked, setPicked] = useState('')
  const [shake, setShake] = useState(false)
  const [pulse, setPulse] = useState(false)
  const [done, setDone] = useState(false)
  const [result, setResult] = useState<{ stars: number; accuracy: number } | null>(null)
  const [open, setOpen] = useState<Place | null>(null)
  const [visited, setVisited] = useState<Set<string>>(new Set())
  const [seconds, setSeconds] = useState(mode === 'flashcards' ? 60 : 0)
  const [started] = useState(() => Date.now())
  const [opts, setOpts] = useState<string[]>([])
  const [side, setSide] = useState<'state' | 'capital'>('state')

  const current = deck[i]

  useEffect(() => {
    if (mode !== 'flashcards' || done) return
    const t = window.setInterval(() => {
      setSeconds((s) => {
        if (s <= 1) {
          window.clearInterval(t)
          return 0
        }
        return s - 1
      })
    }, 1000)
    return () => window.clearInterval(t)
  }, [mode, done])

  useEffect(() => {
    if (mode === 'flashcards' && seconds === 0 && !done && i >= 0) {
      void finish(score, Math.max(score, 1))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seconds])

  useEffect(() => {
    if (mode === 'name_the_capital' && current) setOpts(choicesFor(current, places))
    if (mode === 'flashcards') setSide(Math.random() < 0.5 ? 'state' : 'capital')
  }, [i, mode, current, places])

  const finish = async (finalScore: number, finalTotal: number, extra: Record<string, unknown> = {}) => {
    if (done) return
    setDone(true)
    const secondsUsed = Math.round((Date.now() - started) / 1000)
    try {
      const res = await postJson<{ stars_earned: number; accuracy: number }>(`/api/activities/${activity.activity_id}/attempt`, {
        csrf,
        mode,
        score: finalScore,
        total: finalTotal,
        time_taken_seconds: secondsUsed,
        visited: visited.size,
        detail: extra,
      })
      setResult({ stars: res.stars_earned, accuracy: res.accuracy })
      if (res.stars_earned >= 2) playFx('star', soundOn)
    } catch {
      setResult({ stars: finalScore > 0 ? 1 : 0, accuracy: finalTotal ? (finalScore / finalTotal) * 100 : 0 })
    }
  }

  const markRight = (id: string) => {
    playFx('correct', soundOn)
    setPulse(true)
    window.setTimeout(() => setPulse(false), 350)
    setStatus((s) => ({ ...s, [id]: 'right' }))
    setScore((n) => n + 1)
    setStreak((n) => n + 1)
    setMisses(0)
    setTries(0)
  }

  const markWrong = (id: string) => {
    playFx('miss', soundOn)
    setShake(true)
    window.setTimeout(() => setShake(false), 400)
    setStatus((s) => ({ ...s, [id]: 'wrong' }))
    setStreak(0)
    setMisses((n) => n + 1)
    setTries((n) => n + 1)
  }

  const next = (nextScore = score + 1) => {
    if (i + 1 >= deck.length) {
      void finish(nextScore, deck.length)
      return
    }
    setI((n) => n + 1)
    setPicked('')
    setTries(0)
    setStatus({})
  }

  const onMapPick = (id: string) => {
    if (done) return
    if (mode === 'study') {
      const place = places.find((p) => p.id === id)
      if (place) {
        setOpen(place)
        setVisited((v) => new Set(v).add(id))
      }
      return
    }
    if (mode !== 'find_on_map' || !current) return
    setPicked(id)
    if (id === current.id) {
      markRight(id)
      window.setTimeout(() => next(score + 1), 550)
    } else {
      markWrong(id)
      if (tries + 1 >= 2) {
        setStatus((s) => ({ ...s, [current.id]: 'right', [id]: 'wrong' }))
        window.setTimeout(() => next(score), 900)
      }
    }
  }

  const pickCapital = (text: string) => {
    if (!current || done) return
    if (text === current.capital) {
      markRight(current.id)
      window.setTimeout(() => next(score + 1), 450)
    } else {
      markWrong(current.id)
      if (tries + 1 >= 2) window.setTimeout(() => next(score), 800)
    }
  }

  const flipAnswer = (yes: boolean) => {
    if (!current || done) return
    if (yes) {
      markRight(current.id)
      window.setTimeout(() => next(score + 1), 300)
    } else {
      markWrong(current.id)
      window.setTimeout(() => next(score), 300)
    }
  }

  if (done && result) {
    return (
      <section className="panel finish-card">
        <StarBurst stars={result.stars} />
        <h2>{MODE_LABEL[mode]} — done</h2>
        <p className="grade-big">
          <Stars count={result.stars} />
        </p>
        {mode !== 'study' ? (
          <p className="muted">
            {score} right · {result.accuracy}%
          </p>
        ) : (
          <p className="muted">You opened {visited.size} states.</p>
        )}
        <div className="btn-row">
          <button type="button" className="btn btn--primary" onClick={onExit}>
            Play again
          </button>
          <button type="button" className="btn btn--ghost" onClick={onExit}>
            Try another mode
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className={`panel drill ${shake ? 'is-shake' : ''} ${pulse ? 'is-pulse' : ''}`}>
      <div className="panel__head">
        <h2>{MODE_LABEL[mode]}</h2>
        <button type="button" className="btn btn--small btn--ghost" onClick={onExit}>
          Change mode
        </button>
      </div>
      {mode !== 'study' ? (
        <DrillHud
          progress={mode === 'flashcards' ? score : i}
          total={mode === 'flashcards' ? Math.max(score, 1) : deck.length}
          streak={streak}
          misses={misses}
          seconds={mode === 'flashcards' ? seconds : undefined}
        />
      ) : (
        <p className="muted">Opened {visited.size} of {places.length}. Open 10 to earn a star for studying.</p>
      )}

      {mode === 'find_on_map' && current ? (
        <p className="prompt-line">
          Find the state whose capital is <strong>{current.capital}</strong>
        </p>
      ) : null}
      {mode === 'name_the_capital' && current ? (
        <p className="prompt-line">
          What is the capital of <strong>{current.name}</strong>?
        </p>
      ) : null}
      {mode === 'flashcards' && current ? (
        <p className="prompt-line">
          {side === 'state' ? (
            <>
              Capital of <strong>{current.name}</strong>?
            </>
          ) : (
            <>
              Which state has capital <strong>{current.capital}</strong>?
            </>
          )}
        </p>
      ) : null}

      {mode === 'study' || mode === 'find_on_map' || mode === 'name_the_capital' ? (
        <UsaMap
          places={places}
          selected={picked || open?.id}
          highlight={mode === 'name_the_capital' ? current?.id : undefined}
          status={status}
          regionTint={mode === 'study'}
          onPick={onMapPick}
        />
      ) : null}

      {mode === 'study' && open ? (
        <article className="state-card">
          <h3 className="wrap-any">{open.name}</h3>
          <p className="grade-big wrap-any">{open.capital}</p>
          <p className="muted">{open.capital_phonetic}</p>
          <p className="wrap-any">{open.tip}</p>
          <p className="muted">{open.region}</p>
        </article>
      ) : null}

      {mode === 'name_the_capital' ? (
        <div className="choice-grid">
          {opts.map((c) => (
            <button key={c} type="button" className="btn" onClick={() => pickCapital(c)}>
              {c}
            </button>
          ))}
        </div>
      ) : null}

      {mode === 'flashcards' && current ? (
        <div className="flash-card">
          <p className="muted">{side === 'state' ? current.capital_phonetic : current.name}</p>
          <div className="btn-row">
            <button type="button" className="btn btn--primary" onClick={() => flipAnswer(true)}>
              I got it
            </button>
            <button type="button" className="btn" onClick={() => flipAnswer(false)}>
              Show me
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => next(score)}>
              Skip
            </button>
          </div>
          {tries > 0 ? (
            <p>
              {current.name} — {current.capital}
            </p>
          ) : null}
        </div>
      ) : null}

      {mode === 'find_on_map' && tries >= 2 && current ? (
        <p className="muted">
          {current.capital} is the capital of {current.name}.
        </p>
      ) : null}

      {mode === 'study' ? (
        <button
          type="button"
          className="btn"
          onClick={() => void finish(visited.size, places.length, { visited: visited.size })}
          disabled={visited.size < 10}
        >
          I studied enough
        </button>
      ) : null}
    </section>
  )
}
