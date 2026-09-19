export function DrillHud({
  progress,
  total,
  streak,
  misses,
  seconds,
}: {
  progress: number
  total: number
  streak: number
  misses?: number
  seconds?: number
}) {
  return (
    <div className="drill-hud" aria-live="polite">
      <span>
        <strong>{progress}</strong> / {total}
      </span>
      <span>Streak {streak}</span>
      {misses != null ? <span>Misses {misses}</span> : null}
      {seconds != null ? <span>{seconds}s</span> : null}
    </div>
  )
}

export function Stars({ count }: { count: number }) {
  return (
    <span className="star-row" aria-label={`${count} stars`}>
      {[1, 2, 3].map((n) => (
        <span key={n} className={n <= count ? 'star is-on' : 'star'}>
          ★
        </span>
      ))}
    </span>
  )
}
