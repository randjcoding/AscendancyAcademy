import { useState } from 'react'
import { api, postJson } from '../api'
import { MODE_LABEL, type Mode } from './modes'
import { PATH_GAMES, PATH_PASS, PATH_REGIONS, priorRegionIds, type PathRegionId } from './pathRegions'
import { PlayRound, pathDeck, type Place } from './ActivityRunner'
import { UsaMap } from './UsaMap'

export type PathGameScore = Partial<Record<(typeof PATH_GAMES)[number], number | null>>

export type PathRegion = {
  id: PathRegionId
  label: string
  ids: string[]
  intro_done: boolean
  games: PathGameScore
  passed: boolean
  unlocked: boolean
}

export type PathState = {
  regions: PathRegion[]
  final: PathGameScore
  final_open: boolean
  beaten: boolean
  games: string[]
  pass: number
}

type Step =
  | { kind: 'home' }
  | { kind: 'intro'; region: PathRegion }
  | { kind: 'ready'; region: PathRegion | 'final'; mode: Mode; label: string }
  | { kind: 'play'; region: PathRegion | 'final'; mode: Mode }
  | { kind: 'retry'; region: PathRegion | 'final'; mode: Mode; firstPass: number }

function nextGame(games: PathGameScore): Mode | null {
  for (const mode of PATH_GAMES) {
    if ((games[mode] ?? 0) < PATH_PASS) return mode
  }
  return null
}

export function LearningPath({
  places,
  csrf,
  activityId,
  soundOn,
  spellHelp = true,
  path,
  onChange,
}: {
  places: Place[]
  csrf: string
  activityId: string
  soundOn: boolean
  spellHelp?: boolean
  path: PathState
  onChange: (next: PathState) => void
}) {
  const [step, setStep] = useState<Step>({ kind: 'home' })
  const [introI, setIntroI] = useState(0)
  const [error, setError] = useState('')

  const startRegion = (region: PathRegion) => {
    if (!region.unlocked) return
    if (!region.intro_done) {
      setIntroI(0)
      setStep({ kind: 'intro', region })
      return
    }
    const mode = nextGame(region.games)
    if (mode) setStep({ kind: 'ready', region, mode, label: MODE_LABEL[mode] })
  }

  const finishIntro = async (region: PathRegion) => {
    try {
      const res = await postJson<{ path: PathState }>(`/api/activities/${activityId}/path`, {
        csrf,
        region: region.id,
        intro_done: true,
      })
      onChange(res.path)
      const mode = nextGame(res.path.regions.find((r) => r.id === region.id)?.games || region.games)
      if (mode) setStep({ kind: 'ready', region: { ...region, intro_done: true }, mode, label: MODE_LABEL[mode] })
      else setStep({ kind: 'home' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save that.')
    }
  }

  const deckFor = (region: PathRegion | 'final') => {
    if (region === 'final') return places
    const review = priorRegionIds(region.id)
    return pathDeck(places, region.id, review)
  }

  if (step.kind === 'intro') {
    const states = PATH_REGIONS.find((r) => r.id === step.region.id)?.ids || []
    const id = states[introI]
    const place = places.find((p) => p.id === id)
    if (!place) return null
    const last = introI + 1 >= states.length
    return (
      <section className="panel">
        <div className="panel__head">
          <h2>Say it — {step.region.label}</h2>
          <button type="button" className="btn btn--small btn--ghost" onClick={() => setStep({ kind: 'home' })}>
            Back
          </button>
        </div>
        <p className="prompt-line">
          Look at <strong>{place.name}</strong>. Say the state and the capital out loud three times: {place.name}, {place.capital}.
        </p>
        <div className="study-desk">
          <UsaMap
            places={places}
            selected={place.id}
            highlight={place.id}
            labels
            tips
            zoomId={step.region.id}
            onPick={() => undefined}
          />
          <aside className="state-card state-card--side">
            <p className="muted">{step.region.label}</p>
            <h3 className="wrap-any">{place.name}</h3>
            <p className="grade-big wrap-any">{place.capital}</p>
            <p className="muted">{place.capital_phonetic}</p>
            <p className="wrap-any">{place.tip}</p>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => {
                if (last) void finishIntro(step.region)
                else setIntroI((n) => n + 1)
              }}
            >
              I said it three times
            </button>
          </aside>
        </div>
        <p className="muted">{introI + 1} of {states.length}</p>
      </section>
    )
  }

  if (step.kind === 'ready') {
    return (
      <section className="panel">
        <h2>{step.region === 'final' ? 'Beat the country' : step.region.label}</h2>
        <p>
          Ready for {step.label}? Get 90% on the first try to move on. Misses come back after the next question.
        </p>
        {error ? <div className="status status--error">{error}</div> : null}
        <div className="btn-row">
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => setStep({ kind: 'play', region: step.region, mode: step.mode })}
          >
            I am ready
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => setStep({ kind: 'home' })}>
            Not yet
          </button>
        </div>
      </section>
    )
  }

  if (step.kind === 'retry') {
    return (
      <section className="panel">
        <h2>Try {MODE_LABEL[step.mode]} again</h2>
        <p>First try was {Math.round(step.firstPass)}%. You need {PATH_PASS}% to unlock the next piece.</p>
        <div className="btn-row">
          <button type="button" className="btn btn--primary" onClick={() => setStep({ kind: 'play', region: step.region, mode: step.mode })}>
            Go again
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => setStep({ kind: 'home' })}>
            Back to the path
          </button>
        </div>
      </section>
    )
  }

  if (step.kind === 'play') {
    const deck = deckFor(step.region)
    return (
      <PlayRound
        key={`${step.region === 'final' ? 'final' : step.region.id}-${step.mode}`}
        mode={step.mode}
        batch={deck.length}
        timer={60}
        showLabels={false}
        places={deck}
        allPlaces={places}
        activityId={activityId}
        csrf={csrf}
        soundOn={soundOn}
        spellHelp={spellHelp}
        startRegion={step.region === 'final' ? 'whole' : step.region.id}
        path={step.region === 'final' ? { final: true } : { region: step.region.id }}
        onExit={() => setStep({ kind: 'home' })}
        onFinished={({ firstPass }) => {
          void api<{ path: PathState }>(`/api/activities/${activityId}/path`).then((d) => {
            if (d.path) onChange(d.path)
          })
          if (firstPass + 1e-9 >= PATH_PASS) {
            const scores = {
              ...(step.region === 'final' ? path.final : step.region.games),
              [step.mode]: firstPass,
            }
            const nextMode = nextGame(scores)
            if (nextMode) setStep({ kind: 'ready', region: step.region, mode: nextMode, label: MODE_LABEL[nextMode] })
            else setStep({ kind: 'home' })
          } else {
            setStep({ kind: 'retry', region: step.region, mode: step.mode, firstPass })
          }
        }}
      />
    )
  }

  return (
    <section className="panel path-trail">
      <h2>Learn the country</h2>
      <p className="muted">
        One group at a time. Say the names, then play the six games to 90%. Type it out, speed round, and who lives next door stay extra practice.
      </p>
      {path.beaten ? <p className="streak-chip">You beat the country.</p> : null}
      <ol className="path-list">
        {path.regions.map((region) => (
          <li key={region.id} className={`path-item ${region.unlocked ? 'is-open' : 'is-lock'} ${region.passed ? 'is-done' : ''}`}>
            <button type="button" className="path-item__btn" disabled={!region.unlocked} onClick={() => startRegion(region)}>
              <strong className="wrap-any">{region.label}</strong>
              <span className="muted">
                {!region.unlocked
                  ? 'Locked'
                  : region.passed
                    ? 'Done'
                    : region.intro_done
                      ? `${PATH_GAMES.filter((g) => (region.games[g] ?? 0) >= PATH_PASS).length} of ${PATH_GAMES.length} games`
                      : 'Say the names first'}
              </span>
            </button>
          </li>
        ))}
        <li className={`path-item ${path.final_open ? 'is-open' : 'is-lock'} ${path.beaten ? 'is-done' : ''}`}>
          <button
            type="button"
            className="path-item__btn"
            disabled={!path.final_open}
            onClick={() => {
              const mode = nextGame(path.final)
              if (mode) setStep({ kind: 'ready', region: 'final', mode, label: MODE_LABEL[mode] })
            }}
          >
            <strong>Beat the country</strong>
            <span className="muted">{path.beaten ? 'Done' : path.final_open ? 'All 50, six games' : 'Locked until every group is done'}</span>
          </button>
        </li>
      </ol>
    </section>
  )
}
