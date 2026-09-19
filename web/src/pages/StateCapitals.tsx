import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api'
import { useAuth } from '../Auth'
import { ActivityRunner, type ActivityPayload, type StruggleItem } from '../activities/ActivityRunner'
import { LearningPath, type PathState } from '../activities/LearningPath'
import { Stars } from '../activities/DrillHud'

export function StateCapitals() {
  const { user } = useAuth()
  const [activity, setActivity] = useState<ActivityPayload | null>(null)
  const [stars, setStars] = useState(0)
  const [struggle, setStruggle] = useState<StruggleItem[]>([])
  const [path, setPath] = useState<PathState | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api<{ activity: ActivityPayload; struggle?: StruggleItem[]; path?: PathState | null }>('/api/activities/us-state-capitals')
      .then((d) => {
        setActivity(d.activity)
        setStars(d.activity.best_stars || 0)
        setStruggle(d.struggle || [])
        setPath(d.path || null)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load that activity.'))
  }, [])

  if (!activity) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <h1>{activity.title}</h1>
          <p className="muted">Learn the states and the capitals. Click them, type them, and watch the ones that keep slipping.</p>
        </div>
        <div>
          <Stars count={stars} />
          <p className="btn-row">
            <Link to="/activities/progress" className="btn">What needs work</Link>
            <Link to="/activities" className="btn btn--ghost">All activities</Link>
          </p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      {struggle.filter((s) => s.wrong > 0).length ? (
        <p className="muted">
          {struggle.filter((s) => s.wrong > 0).length} states still need work.{' '}
          <Link to="/activities/progress">See the list</Link>
        </p>
      ) : null}
      {path ? (
        <LearningPath
          places={activity.content}
          csrf={user?.csrf || ''}
          activityId={activity.activity_id}
          soundOn={user?.sound_enabled !== false}
          path={path}
          onChange={setPath}
        />
      ) : null}
      <ActivityRunner activity={activity} csrf={user?.csrf || ''} soundOn={user?.sound_enabled !== false} struggle={struggle} />
    </>
  )
}
