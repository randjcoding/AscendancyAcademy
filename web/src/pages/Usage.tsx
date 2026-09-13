import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'

type Row = { when: string; who: string; model: string; purpose: string; tokens: number; usd: number; status: string }

export function Usage() {
  const [rows, setRows] = useState<Row[]>([])
  const [total, setTotal] = useState(0)
  const [label, setLabel] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api<{ rows: Row[]; month_total: number; month_label: string }>('/api/usage')
      .then((data) => {
        setRows(data.rows)
        setTotal(data.month_total)
        setLabel(data.month_label)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Could not load usage.'))
  }, [])

  return (
    <>
      <header className="page-head">
        <div>
          <h1>AI Usage</h1>
          <p className="muted">{label} · ${total.toFixed(3)} logged</p>
        </div>
      </header>
      {error ? <div className="status status--error">{error}</div> : null}
      <div className="table-wrap">
        <table className="sheet">
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>Model</th>
              <th>Tokens</th>
              <th>USD</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.when}-${i}`}>
                <td>{r.when.slice(0, 16).replace('T', ' ')}</td>
                <td className="wrap-text">{r.who}</td>
                <td className="wrap-text">{r.model}</td>
                <td>{r.tokens}</td>
                <td>${Number(r.usd || 0).toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
