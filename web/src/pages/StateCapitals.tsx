import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { useAuth } from '../Auth'
import { ActivityRunner, type ActivityPayload } from '../activities/ActivityRunner'
import { Stars } from '../activities/DrillHud'

export function StateCapitals() {
  const { user } = useAuth()
  const [activity, setActivity] = useState<ActivityPayload | null>(null)
  const [stars, setStars] = useState(0)
  const [error, setError] = useState('')

  useEffect(() => {
    api<{ activity: ActivityPayload }>('/api/activities/us-state-capitals')
      .then((d) => {
        setActivity(d.activity)
        setStars(d.activity.best_stars || 0)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load that activity.'))
  }, [])

  if (!activity) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <h1>{activity.title}</h1>
          <p className="muted">Fifty states. Four ways to practice. Learn the map, then race the clock.</p>
        </div>
        <div>
          <Stars count={stars} />
          <p><Link to="/activities" className="btn btn--ghost">All activities</Link></p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <ActivityRunner activity={activity} csrf={user?.csrf || ''} soundOn={user?.sound_enabled !== false} />
    </>
  )
}
