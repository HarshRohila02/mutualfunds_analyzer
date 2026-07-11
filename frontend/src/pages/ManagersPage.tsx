import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtNum, fmtPct, type ManagerScore, type ManagerSummary } from '../api'

export default function ManagersPage() {
  const [managers, setManagers] = useState<ManagerSummary[]>([])
  const [scores, setScores] = useState<Record<number, ManagerScore>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .managers()
      .then(async (list) => {
        setManagers(list)
        const detail = await Promise.all(list.map((m) => api.manager(m.manager_id)))
        setScores(Object.fromEntries(detail.map((d) => [d.manager_id, d])))
      })
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <div className="state-note error">Could not load managers: {error}</div>

  const ranked = managers
    .map((m) => scores[m.manager_id])
    .filter((s): s is ManagerScore => s != null)
    .sort((a, b) => (b.composite ?? -1) - (a.composite ?? -1))

  return (
    <>
      <div className="section-head" style={{ marginTop: 8 }}>
        <h2>Fund managers on record</h2>
        <span className="muted" style={{ fontSize: 13 }}>
          curated dataset · scores isolate each manager's actual tenure window
        </span>
      </div>
      <div className="caveat" style={{ maxWidth: 720 }}>
        This list is a hand-curated seed, not full industry coverage. A manager's score ranks
        their fund's Sharpe against category peers over the same calendar window they actually
        managed it — inherited track records don't count.
      </div>
      {ranked.length === 0 && <div className="state-note">Loading manager scores…</div>}
      {ranked.map((m) => (
        <div className="card" key={m.manager_id} style={{ marginBottom: 14 }}>
          <div className="manager-block">
            <h3 className="manager-name">{m.name}</h3>
            <div className="muted" style={{ fontSize: 13 }}>
              {m.amc}
              {m.career_start_year ? ` · in markets since ${m.career_start_year}` : ''}
            </div>
            <div className="manager-scores">
              <div className="item">
                <div className="k">Composite</div>
                <div className="v">{m.composite ?? '—'}</div>
              </div>
              <div className="item">
                <div className="k">Tenure</div>
                <div className="v">{m.tenure_score ?? '—'}</div>
              </div>
              <div className="item">
                <div className="k">Performance</div>
                <div className="v">{m.performance_score ?? '—'}</div>
              </div>
            </div>
            {m.assignments.map((a) => (
              <div className="assignment" key={a.scheme_code}>
                <div className="line">
                  <span>
                    <Link to={`/fund/${a.scheme_code}`}>{a.scheme_name}</Link>
                    <span className="muted">
                      {' '}
                      · {a.start_date.slice(0, 7)} → {a.end_date?.slice(0, 7) ?? 'now'}
                    </span>
                  </span>
                  {a.skipped_reason ? (
                    <span className="muted">not scored</span>
                  ) : (
                    <span className="nums">
                      {fmtPct(a.tenure_cagr)} · Sharpe {fmtNum(a.tenure_sharpe)} ·{' '}
                      {a.peer_percentile != null
                        ? `${a.peer_percentile.toFixed(0)} pct`
                        : 'no rank'}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </>
  )
}
