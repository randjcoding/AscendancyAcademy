import { useEffect, useMemo, useRef, useState } from 'react'
import { postJson } from '../api'
import { DrillHud, Stars } from './DrillHud'
import { MatchBoard } from './MatchBoard'
import { ModePreview } from './ModePreview'
import { MODE_INFO, MODE_LABEL, type Mode } from './modes'
import { USA_NEIGHBORS } from './maps/usaNeighbors'
import { PATH_REGION_IDS, PATH_REGIONS, type PathRegionId } from './pathRegions'
import { playFx } from './sound'
import { StarBurst } from './StarBurst'
import { UsaMap } from './UsaMap'
import { WordBook, spellingMatch } from './WordBook'

export type Place = {
  id: string
  name: string
  capital: string
  capital_phonetic: string
  tip: string
  region: string
  path_region?: string
  trap_city?: string
}

export type ActivityPayload = {
  activity_id: string
  title: string
  modes: string[]
  content: Place[]
  best_stars?: number
}

export type StruggleItem = {
  id: string
  name: string
  capital: string
  seen: number
  correct: number
  wrong: number
  miss_rate: number
}

export type PathDetail = { region?: string; final?: boolean }

const BATCH_CHIPS = [5, 10, 25, 50]
const TIMER_CHIPS = [15, 30, 45, 60, 90, 120]

function shuffle<T>(items: T[]): T[] {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy
}

function regionOf(place: Place): string {
  return place.path_region || PATH_REGION_IDS[place.id] || ''
}

export function filterPlaces(places: Place[], regionId: string): Place[] {
  if (!regionId || regionId === 'whole') return places
  return places.filter((p) => regionOf(p) === regionId)
}

function choicesFor(place: Place, all: Place[], field: 'capital' | 'name'): string[] {
  const same = all.filter((p) => p.id !== place.id && regionOf(p) === regionOf(place))
  const rest = all.filter((p) => p.id !== place.id && regionOf(p) !== regionOf(place))
  const pool = shuffle([...same, ...rest]).slice(0, 3).map((p) => p[field])
  return shuffle([place[field], ...pool])
}

function trapChoices(place: Place, all: Place[]): string[] {
  const trap = place.trap_city || ''
  const others = shuffle(all.filter((p) => p.id !== place.id)).slice(0, trap ? 2 : 3).map((p) => p.capital)
  return shuffle([place.capital, trap, ...others].filter(Boolean)).slice(0, 4)
}

function buildDeck(places: Place[], batch: number, hardIds: string[], hardFirst: boolean): Place[] {
  const n = Math.min(Math.max(1, batch), places.length)
  if (!hardFirst || !hardIds.length) return shuffle(places).slice(0, n)
  const hard = shuffle(places.filter((p) => hardIds.includes(p.id)))
  const rest = shuffle(places.filter((p) => !hardIds.includes(p.id)))
  return [...hard, ...rest].slice(0, n)
}

export function ActivityRunner({
  activity,
  csrf,
  soundOn,
  spellHelp = true,
  onSpellHelp,
  spellHelpLabel,
  struggle = [],
}: {
  activity: ActivityPayload
  csrf: string
  soundOn: boolean
  spellHelp?: boolean
  onSpellHelp?: (on: boolean) => void
  spellHelpLabel?: string
  struggle?: StruggleItem[]
}) {
  const [mode, setMode] = useState<Mode | ''>('')
  const [batch, setBatch] = useState(10)
  const [customCount, setCustomCount] = useState('10')
  const [timer, setTimer] = useState(60)
  const [customTimer, setCustomTimer] = useState('60')
  const [showLabels, setShowLabels] = useState(true)
  const [hardFirst, setHardFirst] = useState(false)
  const [playRegion, setPlayRegion] = useState('whole')
  const hardIds = struggle.filter((s) => s.wrong > 0).map((s) => s.id)
  const pool = filterPlaces(activity.content, playRegion)

  const applyCount = (n: number) => {
    const next = Math.min(50, Math.max(1, Math.round(n) || 1))
    setBatch(next)
    setCustomCount(String(next))
  }
  const applyTimer = (n: number) => {
    const next = Math.min(300, Math.max(10, Math.round(n) || 60))
    setTimer(next)
    setCustomTimer(String(next))
  }

  if (!mode) {
    return (
      <section className="panel">
        <h2>Pick a way to play</h2>
        <div className="mode-grid">
          {MODE_INFO.filter((m) => !activity.modes?.length || activity.modes.includes(m.id)).map((m) => (
            <button key={m.id} type="button" className="mode-card" onClick={() => setMode(m.id)}>
              <ModePreview mode={m.id} />
              <strong>{m.title}</strong>
              <span className="muted">{m.blurb}</span>
            </button>
          ))}
        </div>
        <fieldset className="batch-pick">
          <legend>Which part of the map</legend>
          <div className="btn-row">
            <button type="button" className={`btn ${playRegion === 'whole' ? 'btn--primary' : ''}`} onClick={() => setPlayRegion('whole')}>
              Whole map
            </button>
            {PATH_REGIONS.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`btn ${playRegion === r.id ? 'btn--primary' : ''}`}
                onClick={() => setPlayRegion(r.id)}
              >
                {r.label}
              </button>
            ))}
          </div>
          <p className="muted">
            {playRegion === 'whole' ? 'Questions can be any of the 50.' : `Questions stay in ${PATH_REGIONS.find((r) => r.id === playRegion)?.label}.`}
          </p>
        </fieldset>
        <fieldset className="batch-pick">
          <legend>How many this round</legend>
          <div className="btn-row">
            {BATCH_CHIPS.map((n) => (
              <button key={n} type="button" className={`btn ${batch === n ? 'btn--primary' : ''}`} onClick={() => applyCount(n)}>
                {n === 50 ? 'All 50' : n}
              </button>
            ))}
          </div>
          <label className="field">
            <span className="field__label">Or type any number</span>
            <input
              className="input"
              type="number"
              min={1}
              max={50}
              value={customCount}
              onChange={(e) => setCustomCount(e.target.value)}
              onBlur={() => applyCount(Number(customCount))}
            />
          </label>
        </fieldset>
        <fieldset className="batch-pick">
          <legend>Speed-round timer</legend>
          <div className="btn-row">
            {TIMER_CHIPS.map((n) => (
              <button key={n} type="button" className={`btn ${timer === n ? 'btn--primary' : ''}`} onClick={() => applyTimer(n)}>
                {n}s
              </button>
            ))}
          </div>
          <label className="field">
            <span className="field__label">Or type seconds</span>
            <input
              className="input"
              type="number"
              min={10}
              max={300}
              value={customTimer}
              onChange={(e) => setCustomTimer(e.target.value)}
              onBlur={() => applyTimer(Number(customTimer))}
            />
          </label>
        </fieldset>
        <label className="check-row">
          <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} />
          Show state names and capitals on the study map
        </label>
        {hardIds.length ? (
          <label className="check-row">
            <input type="checkbox" checked={hardFirst} onChange={(e) => setHardFirst(e.target.checked)} />
            Start with the ones that need work ({hardIds.length})
          </label>
        ) : null}
        {onSpellHelp ? (
          <label className="check-row">
            <input type="checkbox" checked={spellHelp} onChange={(e) => onSpellHelp(e.target.checked)} />
            {spellHelpLabel || 'Help with spelling'}
          </label>
        ) : null}
        <p className="muted">
          {spellHelp
            ? 'Type it out uses a word book so a missed letter does not count as a miss. A parent can turn that off.'
            : 'Spelling help is off. Type it out needs the exact name.'}
        </p>
      </section>
    )
  }
  return (
    <PlayRound
      key={`${mode}-${batch}-${timer}-${hardFirst}-${playRegion}`}
      mode={mode}
      batch={batch}
      timer={timer}
      showLabels={showLabels}
      hardFirst={hardFirst}
      hardIds={hardIds}
      places={pool}
      allPlaces={activity.content}
      activityId={activity.activity_id}
      csrf={csrf}
      soundOn={soundOn}
      spellHelp={spellHelp}
      startRegion={playRegion}
      onExit={() => setMode('')}
    />
  )
}

export function PlayRound({
  mode,
  batch,
  timer,
  showLabels,
  hardFirst = false,
  hardIds = [],
  places,
  allPlaces,
  activityId,
  csrf,
  soundOn,
  spellHelp = true,
  startRegion = 'whole',
  path,
  onExit,
  onFinished,
}: {
  mode: Mode
  batch: number
  timer: number
  showLabels: boolean
  hardFirst?: boolean
  hardIds?: string[]
  places: Place[]
  allPlaces: Place[]
  activityId: string
  csrf: string
  soundOn: boolean
  spellHelp?: boolean
  startRegion?: string
  path?: PathDetail
  onExit: () => void
  onFinished?: (info: { firstPass: number; score: number; total: number }) => void
}) {
  const seed = useMemo(() => buildDeck(places, Math.min(batch, places.length || 1), hardIds, hardFirst), [places, batch, hardIds, hardFirst])
  const [queue, setQueue] = useState<Place[]>(() => [...seed])
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
  const [result, setResult] = useState<{ stars: number; accuracy: number; firstPass: number } | null>(null)
  const [open, setOpen] = useState<Place | null>(null)
  const [visited, setVisited] = useState<Set<string>>(new Set())
  const [seconds, setSeconds] = useState(mode === 'flashcards' ? timer : 0)
  const [started] = useState(() => Date.now())
  const [opts, setOpts] = useState<string[]>([])
  const [side, setSide] = useState<'state' | 'capital'>('state')
  const [quizAsk, setQuizAsk] = useState<'capital' | 'state'>('capital')
  const [labelsOn, setLabelsOn] = useState(showLabels)
  const [typed, setTyped] = useState('')
  const [zoomId, setZoomId] = useState(startRegion)
  const itemLog = useRef<{ id: string; correct: boolean }[]>([])
  const firstTry = useRef<Record<string, boolean>>({})
  const finished = useRef(false)
  const [uniqueTotal, setUniqueTotal] = useState(seed.length)

  const current = queue[i]
  const revealed = tries >= 2 || (current ? status[current.id] === 'right' : false)

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
      void finish()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seconds])

  useEffect(() => {
    if (!current) return
    setTyped('')
    if (mode === 'name_the_capital') setOpts(choicesFor(current, allPlaces, 'capital'))
    if (mode === 'city_trap') setOpts(trapChoices(current, allPlaces))
    if (mode === 'quiz') {
      const ask = Math.random() < 0.5 ? 'capital' : 'state'
      setQuizAsk(ask)
      setOpts(choicesFor(current, allPlaces, ask === 'capital' ? 'capital' : 'name'))
    }
    if (mode === 'flashcards' || mode === 'type_it') setSide(Math.random() < 0.5 ? 'state' : 'capital')
  }, [i, mode, current, allPlaces])

  const logItem = (id: string, correct: boolean) => {
    itemLog.current = [...itemLog.current, { id, correct }]
    if (!(id in firstTry.current)) firstTry.current[id] = correct
  }

  const firstPassPct = () => {
    const ids = Object.keys(firstTry.current)
    if (!ids.length) return 0
    const right = ids.filter((id) => firstTry.current[id]).length
    return Math.round((right / ids.length) * 1000) / 10
  }

  const finish = async (extra: Record<string, unknown> = {}) => {
    if (finished.current) return
    finished.current = true
    setDone(true)
    const firstPass = firstPassPct()
    const finalScore = mode === 'study' ? visited.size : Object.values(firstTry.current).filter(Boolean).length
    const finalTotal = mode === 'study' ? allPlaces.length : uniqueTotal || Object.keys(firstTry.current).length || 1
    const secondsUsed = Math.round((Date.now() - started) / 1000)
    const pathDetail = path ? { path: { ...path, first_pass: firstPass } } : {}
    try {
      const res = await postJson<{ stars_earned: number; accuracy: number }>(`/api/activities/${activityId}/attempt`, {
        csrf,
        mode,
        score: finalScore,
        total: finalTotal,
        time_taken_seconds: secondsUsed,
        visited: visited.size,
        detail: { ...extra, ...pathDetail, batch, timer, first_pass: firstPass, items: extra.items || itemLog.current },
      })
      setResult({ stars: res.stars_earned, accuracy: res.accuracy, firstPass })
      if (res.stars_earned >= 2) playFx('star', soundOn)
      onFinished?.({ firstPass, score: finalScore, total: finalTotal })
    } catch {
      setResult({ stars: finalScore > 0 ? 1 : 0, accuracy: finalTotal ? (finalScore / finalTotal) * 100 : 0, firstPass })
      onFinished?.({ firstPass, score: finalScore, total: finalTotal })
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
    logItem(id, true)
  }

  const markWrong = (id: string, advanceLog = false) => {
    playFx('miss', soundOn)
    setShake(true)
    window.setTimeout(() => setShake(false), 400)
    setStatus((s) => ({ ...s, [id]: 'wrong' }))
    setStreak(0)
    setMisses((n) => n + 1)
    setTries((n) => n + 1)
    if (advanceLog) logItem(id, false)
  }

  const advance = (missed?: Place) => {
    setQueue((q) => {
      if (!missed) return q
      const copy = [...q]
      copy.splice(Math.min(i + 2, copy.length), 0, missed)
      return copy
    })
    setI((n) => n + 1)
    setPicked('')
    setTries(0)
    setStatus({})
  }

  useEffect(() => {
    if (done || mode === 'match' || mode === 'study' || mode === 'flashcards') return
    if (i >= queue.length && queue.length) void finish()
  }, [i, queue.length, done, mode])

  const neighborOk = (id: string, place: Place) => {
    const nextDoor = USA_NEIGHBORS[place.id] || []
    if (!nextDoor.length) return id === place.id
    return nextDoor.includes(id)
  }

  const onMapPick = (id: string) => {
    if (done) return
    if (mode === 'study') {
      const place = allPlaces.find((p) => p.id === id)
      if (place) {
        setOpen(place)
        setVisited((v) => new Set(v).add(id))
      }
      return
    }
    if (!current) return
    if (mode !== 'find_on_map' && mode !== 'find_the_state' && mode !== 'neighbor_hunt') return
    setPicked(id)
    const ok = mode === 'neighbor_hunt' ? neighborOk(id, current) : id === current.id
    if (ok) {
      markRight(current.id)
      window.setTimeout(() => advance(), 550)
    } else {
      const lastTry = tries + 1 >= 2
      markWrong(current.id, lastTry)
      if (lastTry) {
        setStatus((s) => ({ ...s, [current.id]: 'right', [id]: 'wrong' }))
        window.setTimeout(() => advance(current), 900)
      }
    }
  }

  const pickText = (text: string, right: string, id: string) => {
    if (done || !current) return
    if (text === right) {
      markRight(id)
      window.setTimeout(() => advance(), 450)
    } else {
      const lastTry = tries + 1 >= 2
      markWrong(id, lastTry)
      if (lastTry) window.setTimeout(() => advance(current), 800)
    }
  }

  const flipAnswer = (yes: boolean) => {
    if (!current || done) return
    if (yes) {
      markRight(current.id)
      window.setTimeout(() => advance(), 300)
    } else {
      markWrong(current.id, true)
      window.setTimeout(() => advance(current), 300)
    }
  }

  const submitType = () => {
    if (!current || done) return
    const right = side === 'state' ? current.capital : current.name
    if (spellingMatch(typed, right, spellHelp)) {
      markRight(current.id)
      window.setTimeout(() => advance(), 350)
    } else {
      const lastTry = tries + 1 >= 2
      markWrong(current.id, lastTry)
      if (lastTry) window.setTimeout(() => advance(current), 800)
    }
  }

  const applyZoom = (id: string) => {
    setZoomId(id)
    if (mode === 'study' || done) return
    const nextPlaces = filterPlaces(allPlaces, id)
    if (!nextPlaces.length) return
    const keptHard = hardIds.filter((hid) => nextPlaces.some((p) => p.id === hid))
    const nextDeck = buildDeck(nextPlaces, Math.min(batch, nextPlaces.length), keptHard, hardFirst)
    setQueue(nextDeck)
    setUniqueTotal(nextDeck.length)
    setI(0)
    firstTry.current = {}
    itemLog.current = []
    setScore(0)
    setPicked('')
    setTries(0)
    setStatus({})
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
            First try {Math.round(result.firstPass)}% · {Object.values(firstTry.current).filter(Boolean).length} of {uniqueTotal} on the first ask
          </p>
        ) : (
          <p className="muted">You opened {visited.size} states.</p>
        )}
        <div className="btn-row">
          <button type="button" className="btn btn--primary" onClick={onExit}>
            {path ? 'Continue' : 'Play again'}
          </button>
          {!path ? (
            <button type="button" className="btn btn--ghost" onClick={onExit}>
              Try another mode
            </button>
          ) : null}
        </div>
      </section>
    )
  }

  const usesMap = mode === 'study' || mode === 'find_on_map' || mode === 'find_the_state' || mode === 'name_the_capital' || mode === 'neighbor_hunt'
  const unlabeled = mode === 'find_the_state' || mode === 'find_on_map' || mode === 'neighbor_hunt'
  const showFacts = mode === 'study' && open
  const showReveal = Boolean(current && revealed && mode !== 'study')
  return (
    <section className={`panel drill ${shake ? 'is-shake' : ''} ${pulse ? 'is-pulse' : ''}`}>
      <div className="panel__head">
        <h2>{MODE_LABEL[mode]}</h2>
        <button type="button" className="btn btn--small btn--ghost" onClick={onExit}>
          {path ? 'Leave this game' : 'Change mode'}
        </button>
      </div>
      {mode !== 'study' ? (
        <DrillHud
          progress={mode === 'flashcards' ? score : mode === 'match' ? score : Object.keys(firstTry.current).length}
          total={mode === 'flashcards' ? Math.max(score, 1) : uniqueTotal}
          streak={streak}
          misses={misses}
          seconds={mode === 'flashcards' ? seconds : undefined}
        />
      ) : (
        <p className="muted">Opened {visited.size} of {allPlaces.length}. Tap a state to read it. Open 10 to earn a star.</p>
      )}

      {mode === 'find_on_map' && current ? (
        <p className="prompt-line">
          Find the state whose capital is <strong>{current.capital}</strong>
        </p>
      ) : null}
      {mode === 'find_the_state' && current ? (
        <p className="prompt-line">
          Click <strong>{current.name}</strong>
        </p>
      ) : null}
      {mode === 'neighbor_hunt' && current ? (
        <p className="prompt-line">
          {(USA_NEIGHBORS[current.id] || []).length
            ? <>Click a state that touches <strong>{current.name}</strong></>
            : <>This state does not touch another state. Click <strong>{current.name}</strong>.</>}
        </p>
      ) : null}
      {mode === 'name_the_capital' && current ? (
        <p className="prompt-line">
          What is the capital of <strong>{current.name}</strong>?
        </p>
      ) : null}
      {mode === 'quiz' && current ? (
        <p className="prompt-line">
          {quizAsk === 'capital' ? (
            <>What is the capital of <strong>{current.name}</strong>?</>
          ) : (
            <>Which state has the capital <strong>{current.capital}</strong>?</>
          )}
        </p>
      ) : null}
      {mode === 'city_trap' && current ? (
        <p className="prompt-line">
          What is the capital of <strong>{current.name}</strong>? Watch out for the famous city.
        </p>
      ) : null}
      {(mode === 'flashcards' || mode === 'type_it') && current ? (
        <p className="prompt-line">
          {side === 'state' ? (
            <>Capital of <strong>{current.name}</strong>?</>
          ) : (
            <>Which state has capital <strong>{current.capital}</strong>?</>
          )}
        </p>
      ) : null}

      {usesMap ? (
        <div className="study-desk">
          <UsaMap
            places={allPlaces}
            selected={picked || open?.id}
            highlight={mode === 'name_the_capital' || (unlabeled && revealed) ? current?.id : undefined}
            status={status}
            regionTint={mode === 'study'}
            labels={mode === 'study' && labelsOn}
            tips={mode === 'study'}
            zoomId={zoomId}
            onPick={onMapPick}
            onZoom={applyZoom}
          />
          <aside className="state-card state-card--side">
            {mode === 'study' ? (
              <label className="check-row">
                <input type="checkbox" checked={labelsOn} onChange={(e) => setLabelsOn(e.target.checked)} />
                Names and capitals on the map
              </label>
            ) : null}
            {showFacts ? (
              <>
                <p className="muted">{open?.region}</p>
                <h3 className="wrap-any">{open?.name}</h3>
                <p className="grade-big wrap-any">{open?.capital}</p>
                <p className="muted">{open?.capital_phonetic}</p>
                <p className="wrap-any">{open?.tip}</p>
              </>
            ) : null}
            {mode === 'name_the_capital' && current ? (
              <>
                <p className="muted">The yellow state is the one we named. Pick its capital — it is not written here yet.</p>
                <div className="choice-grid">
                  {opts.map((c) => (
                    <button key={c} type="button" className="btn" onClick={() => pickText(c, current.capital, current.id)}>
                      {c}
                    </button>
                  ))}
                </div>
              </>
            ) : null}
            {unlabeled && !showReveal ? (
              <p className="muted">No names on the map. Use the prompt, then tap the state.</p>
            ) : null}
            {showReveal && current && mode !== 'name_the_capital' ? (
              <p className="muted">
                {current.name} — {current.capital}
              </p>
            ) : null}
            {mode === 'study' && !open ? <p className="muted">Tap a state to see its capital. Scroll or pinch if you want a closer look.</p> : null}
          </aside>
        </div>
      ) : null}

      {(mode === 'quiz' || mode === 'city_trap') && current ? (
        <div className="choice-grid choice-grid--big">
          {opts.map((c) => (
            <button
              key={c}
              type="button"
              className="btn"
              onClick={() => pickText(c, mode === 'city_trap' || quizAsk === 'capital' ? current.capital : current.name, current.id)}
            >
              {c}
            </button>
          ))}
        </div>
      ) : null}

      {mode === 'type_it' && current ? (
        <form
          className="type-it"
          onSubmit={(e) => {
            e.preventDefault()
            submitType()
          }}
        >
          <label className="field">
            <span className="field__label">Type your answer</span>
            <input className="input" value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus autoComplete="off" spellCheck={spellHelp} />
          </label>
          {spellHelp ? <WordBook places={places} typed={typed} onPick={setTyped} /> : null}
          <button type="submit" className="btn btn--primary">Check</button>
          {tries > 0 && !spellingMatch(typed, side === 'state' ? current.capital : current.name, spellHelp) ? (
            <p className="muted">
              {tries >= 2 ? `${current.name} — ${current.capital}` : 'Not quite. Try once more.'}
            </p>
          ) : null}
        </form>
      ) : null}

      {mode === 'match' ? (
        <MatchBoard
          places={seed}
          done={done}
          onItem={(id, correct) => logItem(id, correct)}
          onScore={(right, _total, finishedRound) => {
            setScore(right)
            if (right > score) {
              playFx('correct', soundOn)
              setStreak((n) => n + 1)
            } else if (!finishedRound) {
              playFx('miss', soundOn)
              setStreak(0)
              setMisses((n) => n + 1)
            }
            if (finishedRound) void finish()
          }}
        />
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
            <button type="button" className="btn btn--ghost" onClick={() => advance()}>
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

      {mode === 'find_on_map' && revealed && current ? (
        <p className="muted">
          {current.capital} is the capital of {current.name}.
        </p>
      ) : null}
      {mode === 'find_the_state' && revealed && current ? (
        <p className="muted">{current.name} is highlighted now.</p>
      ) : null}
      {mode === 'neighbor_hunt' && revealed && current ? (
        <p className="muted">
          {(USA_NEIGHBORS[current.id] || []).length
            ? `${current.name} touches ${(USA_NEIGHBORS[current.id] || []).join(', ')}.`
            : `${current.name} stands alone.`}
        </p>
      ) : null}
      {mode === 'city_trap' && revealed && current ? (
        <p className="muted">
          {current.capital} is the capital. {current.trap_city ? `${current.trap_city} is the city people mix up.` : ''}
        </p>
      ) : null}
      {mode === 'name_the_capital' && revealed && current ? (
        <p className="muted">{current.capital} is the capital of {current.name}.</p>
      ) : null}

      {mode === 'study' ? (
        <button
          type="button"
          className="btn"
          onClick={() => void finish({ visited: visited.size })}
          disabled={visited.size < 10}
        >
          I studied enough
        </button>
      ) : null}
    </section>
  )
}

export function pathDeck(places: Place[], region: PathRegionId, reviewRegions: PathRegionId[]): Place[] {
  const mine = places.filter((p) => regionOf(p) === region)
  if (!reviewRegions.length) return shuffle(mine)
  const review = shuffle(places.filter((p) => reviewRegions.includes(regionOf(p) as PathRegionId)))
  const take = Math.max(1, Math.floor(mine.length / 3))
  return [...shuffle(mine), ...review.slice(0, take)]
}
