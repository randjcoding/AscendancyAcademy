import { useEffect, useState, type MouseEvent } from 'react'
import { ApiError, api, postJson } from '../api'
import { useAuth } from '../Auth'
import type { DayCell, Totals } from '../types'

const MARK: Record<string, string> = {
  present: 'P',
  absent: 'A',
  sick: 'S',
  excused: 'E',
  off: 'O',
}

function weekday(iso: string) {
  return new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short' })
}

export function AttendanceCell({
  day,
  studentId,
  csrf,
  canEdit,
  compact,
  onChanged,
}: {
  day: DayCell
  studentId: number
  csrf: string
  canEdit: boolean
  compact?: boolean
  onChanged: () => void
}) {
  const cycle = async () => {
    if (!canEdit || day.locked || day.in_month === false) return
    await postJson('/api/attendance/day', { student_id: studentId, on_date: day.date, status: '', csrf })
    onChanged()
  }
  const toggleLock = async (e: MouseEvent) => {
    e.stopPropagation()
    if (!canEdit || !day.recorded) return
    await postJson('/api/attendance/day', {
      student_id: studentId,
      on_date: day.date,
      status: day.locked ? 'unlock' : 'lock',
      csrf,
    })
    onChanged()
  }
  const out = day.in_month === false
  const status = day.status || 'empty'
  return (
    <div
      className={`${compact ? 'week-day' : 'cal-cell'} ${day.is_today ? 'is-today' : ''} ${day.locked ? 'is-locked' : ''} ${out ? 'out' : ''} status-${status}`}
      onClick={() => void cycle()}
      role={canEdit && !out ? 'button' : undefined}
    >
      {day.recorded && canEdit ? (
        <button type="button" className="cal-lock" title={day.locked ? 'Unlock' : 'Lock'} onClick={(e) => void toggleLock(e)}>
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            {day.locked ? (
              <path
                fill="currentColor"
                d="M8 1.5A2.5 2.5 0 0 0 5.5 4v2h-1A1.5 1.5 0 0 0 3 7.5v6A1.5 1.5 0 0 0 4.5 15h7A1.5 1.5 0 0 0 13 13.5v-6A1.5 1.5 0 0 0 11.5 6h-1V4A2.5 2.5 0 0 0 8 1.5Zm-1 2.5A1 1 0 0 1 9 4v2H7V4Z"
              />
            ) : (
              <path
                fill="currentColor"
                d="M8 1.5A2.5 2.5 0 0 0 5.5 4v.75h1.5V4a1 1 0 0 1 2 0v2H4.5A1.5 1.5 0 0 0 3 7.5v6A1.5 1.5 0 0 0 4.5 15h7A1.5 1.5 0 0 0 13 13.5v-6A1.5 1.5 0 0 0 11.5 6H7V4A2.5 2.5 0 0 1 8 1.5Z"
              />
            )}
          </svg>
        </button>
      ) : null}
      <span className={compact ? 'week-day__name' : 'cal-cell__num'}>{compact ? weekday(day.date) : day.day}</span>
      <span className={compact ? 'week-day__mark' : 'cal-cell__mark'}>{MARK[day.status] || '·'}</span>
    </div>
  )
}

type AttData = {
  student: { id: number; name: string } | null
  can_edit: boolean
  view_year: number
  view_month: number
  month_name: string
  totals: Totals | null
  weeks: DayCell[][]
}

export function Attendance() {
  const { user } = useAuth()
  const [data, setData] = useState<AttData | null>(null)
  const [error, setError] = useState('')
  const [year, setYear] = useState<number | undefined>()
  const [month, setMonth] = useState<number | undefined>()

  const load = async (y = year, m = month) => {
    const q = new URLSearchParams()
    if (y) q.set('year', String(y))
    if (m) q.set('month', String(m))
    const row = await api<AttData>(`/api/attendance?${q}`)
    setData(row)
    setYear(row.view_year)
    setMonth(row.view_month)
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load attendance.'))
  }, [])

  const shift = (delta: number) => {
    if (!data) return
    let y = data.view_year
    let m = data.view_month + delta
    if (m < 1) {
      m = 12
      y -= 1
    }
    if (m > 12) {
      m = 1
      y += 1
    }
    void load(y, m)
  }

  if (!data) return error ? <div className="status status--error">{error}</div> : <p className="muted">Loading…</p>

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Attendance</h1>
          <p className="muted">{data.student?.name}</p>
        </div>
        <div className="page-head__actions">
          <a className="btn" href={`/print/attendance/month?year=${data.view_year}&month=${data.view_month}`}>
            Print month
          </a>
          <a className="btn" href="/print/attendance/year">
            Print year
          </a>
        </div>
      </header>
      {data.totals ? (
        <div className="stat-row">
          <div className="stat">
            <strong>{data.totals.present}</strong>
            <span>Present</span>
          </div>
          <div className="stat">
            <strong>{data.totals.remaining}</strong>
            <span>Left toward {data.totals.target}</span>
          </div>
          <div className="stat">
            <strong>{data.totals.absent}</strong>
            <span>Absent</span>
          </div>
        </div>
      ) : null}
      <div className="month-nav">
        <button type="button" className="btn" onClick={() => shift(-1)}>
          Earlier
        </button>
        <h2>
          {data.month_name} {data.view_year}
        </h2>
        <button type="button" className="btn" onClick={() => shift(1)}>
          Later
        </button>
      </div>
      <div className="cal-grid">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
          <div key={d} className="cal-grid__head">
            {d}
          </div>
        ))}
        {data.weeks.flat().map((day) => (
          <AttendanceCell
            key={day.date}
            day={day}
            studentId={data.student?.id || 0}
            csrf={user?.csrf || ''}
            canEdit={data.can_edit}
            onChanged={() => void load()}
          />
        ))}
      </div>
      <p className="muted legend">
        Click a day to cycle Present → Absent → Sick → Excused → Off → clear. The lock keeps a day from changing.
      </p>
    </>
  )
}
