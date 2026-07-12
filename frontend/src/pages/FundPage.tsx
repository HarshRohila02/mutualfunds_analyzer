import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  api,
  fmtNum,
  fmtPct,
  type FundDetail,
  type ManagerScore,
  type NavPoint,
} from '../api'

function PercentileRail({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rail-row">
      <div className="rail-head">
        <span>{label}</span>
        <span className="mono">{value == null ? '—' : `${value.toFixed(0)} pct`}</span>
      </div>
      <div className="rail" role="img" aria-label={`${label}: percentile ${value ?? 'unavailable'}`}>
        {value != null && (
          <>
            <div className="fill" style={{ width: `${value}%` }} />
            <div className="tick" style={{ left: `${value}%` }} />
          </>
        )}
      </div>
    </div>
  )
}

function MetricRow({ k, v, cls }: { k: string; v: string; cls?: string }) {
  return (
    <div className="metric-row">
      <span className="muted">{k}</span>
      <span className={`v ${cls ?? ''}`}>{v}</span>
    </div>
  )
}

function ManagerPanel({ managers }: { managers: ManagerScore[] }) {
  if (managers.length === 0) {
    return (
      <div className="caveat">
        No manager on record for this scheme yet. Manager coverage comes from a small curated
        dataset — absence here says nothing about the fund itself.
      </div>
    )
  }
  return (
    <>
      {managers.map((m) => (
        <div className="manager-block" key={m.manager_id}>
          <h3 className="manager-name">{m.name}</h3>
          <div className="muted" style={{ fontSize: 13 }}>
            {m.amc}
            {m.career_start_year ? ` · in markets since ${m.career_start_year}` : ''}
          </div>
          <div className="manager-scores">
            <div className="item">
              <div className="k">Manager score</div>
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
          {m.bio && <p style={{ fontSize: 13.5, margin: '6px 0' }}>{m.bio}</p>}
          {m.caveats.map((c, i) => (
            <div className="caveat" key={i}>
              {c}
            </div>
          ))}
          <div>
            {m.assignments.map((a) => (
              <div className="assignment" key={a.scheme_code}>
                <div className="line">
                  <span>
                    {a.scheme_name}
                    <span className="muted">
                      {' '}
                      · {a.start_date.slice(0, 7)} → {a.end_date?.slice(0, 7) ?? 'now'}
                    </span>
                  </span>
                  {a.skipped_reason ? (
                    <span className="muted">not scored: {a.skipped_reason}</span>
                  ) : (
                    <span className="nums">
                      {fmtPct(a.tenure_cagr)} CAGR · Sharpe {fmtNum(a.tenure_sharpe)} ·{' '}
                      {a.peer_percentile != null ? `${a.peer_percentile.toFixed(0)} pct of ${a.peer_count} peers` : 'no peer rank'}
                    </span>
                  )}
                </div>
                {a.note && (
                  <div className="muted" style={{ fontSize: 12 }}>
                    {a.note}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </>
  )
}

export default function FundPage() {
  const { code } = useParams<{ code: string }>()
  const [fund, setFund] = useState<FundDetail | null>(null)
  const [nav, setNav] = useState<NavPoint[]>([])
  const [managers, setManagers] = useState<ManagerScore[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!code) return
    setFund(null)
    setError(null)
    api.fund(code).then(setFund).catch((e) => setError(String(e)))
    api.nav(code).then(setNav).catch(() => setNav([]))
    api.managersForScheme(code).then(setManagers).catch(() => setManagers([]))
  }, [code])

  if (error) return <div className="state-note error">Could not load fund: {error}</div>
  if (!fund) return <div className="state-note">Opening the books…</div>

  const m = fund.metrics
  // Downsample long NAV histories for the chart; ~600 points is visually
  // identical to 3000+ at this width and far cheaper to render.
  const step = Math.max(1, Math.floor(nav.length / 600))
  const chartData = nav
    .filter((_, i) => i % step === 0 || i === nav.length - 1)
    .map((p) => ({ date: p.date, nav: p.nav }))

  return (
    <>
      <p className="eyebrow">
        <Link to="/" style={{ textDecoration: 'none' }}>
          ← All funds
        </Link>
      </p>
      <div className="fund-header">
        <div>
          <h1>{fund.scheme_name}</h1>
          <div className="meta">
            {fund.fund_house} · {fund.category ?? 'Uncategorised'} · code{' '}
            <span className="mono">{fund.scheme_code}</span>
            {fund.isin_growth && (
              <>
                {' '}
                · ISIN <span className="mono">{fund.isin_growth}</span>
              </>
            )}
          </div>
          {m && (
            <div className="meta" style={{ marginTop: 6 }}>
              {m.history_years.toFixed(1)} years of NAV · scored against{' '}
              {m.category_peer_count ?? '—'} category peers
            </div>
          )}
        </div>
        <div
          className={`stamp ${m?.fund_score == null ? 'unscored' : ''}`}
          role="img"
          aria-label={`Fund score ${m?.fund_score ?? 'not available'}`}
        >
          <div className="score">{m?.fund_score == null ? '—' : m.fund_score.toFixed(0)}</div>
          <div className="label">{m?.fund_score == null ? 'Unscored' : 'Kosh fund score'}</div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="card full">
          <h2>NAV — full history</h2>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }}
                  tickFormatter={(d: string) => d.slice(0, 4)}
                  minTickGap={40}
                  stroke="#8a8578"
                />
                <YAxis
                  tick={{ fontSize: 11, fontFamily: 'IBM Plex Mono' }}
                  domain={['auto', 'auto']}
                  width={58}
                  stroke="#8a8578"
                />
                <Tooltip
                  formatter={(v) => [`₹${Number(v).toFixed(2)}`, 'NAV']}
                  labelStyle={{ fontFamily: 'IBM Plex Mono', fontSize: 12 }}
                  contentStyle={{
                    background: '#fdfcf9',
                    border: '1px solid #d9d3c6',
                    fontFamily: 'IBM Plex Mono',
                    fontSize: 12,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="nav"
                  stroke="#1c2433"
                  strokeWidth={1.5}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="state-note">No NAV history stored for this scheme.</div>
          )}
        </div>

        <div className="card">
          <h2>Returns &amp; risk</h2>
          {m ? (
            <>
              <MetricRow k="1y CAGR" v={fmtPct(m.cagr_1y)} cls={m.cagr_1y != null && m.cagr_1y < 0 ? 'neg' : 'pos'} />
              <MetricRow k="3y CAGR" v={fmtPct(m.cagr_3y)} cls={m.cagr_3y != null && m.cagr_3y < 0 ? 'neg' : 'pos'} />
              <MetricRow k="5y CAGR" v={fmtPct(m.cagr_5y)} cls={m.cagr_5y != null && m.cagr_5y < 0 ? 'neg' : 'pos'} />
              <MetricRow k="10y CAGR" v={fmtPct(m.cagr_10y)} cls={m.cagr_10y != null && m.cagr_10y < 0 ? 'neg' : 'pos'} />
              <MetricRow k="Annualised volatility" v={fmtPct(m.ann_volatility)} />
              <MetricRow k="Max drawdown" v={fmtPct(m.max_drawdown)} cls="neg" />
              <MetricRow k="Sharpe (3y)" v={fmtNum(m.sharpe_3y)} />
              <MetricRow k="Sortino (3y)" v={fmtNum(m.sortino_3y)} />
              <MetricRow
                k="Rolling 3y windows positive"
                v={m.rolling_3y_positive_pct == null ? '—' : fmtPct(m.rolling_3y_positive_pct, 0)}
              />
              <MetricRow k="Median rolling 3y CAGR" v={fmtPct(m.rolling_3y_median_cagr)} />
            </>
          ) : (
            <div className="state-note">
              Not enough NAV history to compute metrics (needs at least a year).
            </div>
          )}
        </div>

        <div className="card">
          <h2>Standing among peers</h2>
          {m && m.fund_score != null ? (
            <>
              <PercentileRail label="3y return" value={m.pct_cagr_3y} />
              <PercentileRail label="Sharpe" value={m.pct_sharpe_3y} />
              <PercentileRail label="Sortino" value={m.pct_sortino_3y} />
              <PercentileRail label="Drawdown resilience" value={m.pct_max_drawdown} />
              <PercentileRail label="Consistency" value={m.pct_consistency} />
              <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
                Percentile within “{m.score_category}” ({m.category_peer_count} peers). The
                composite blends these: Sharpe 30%, consistency 20%, Sortino 20%, return 15%,
                drawdown 15%.
              </p>
            </>
          ) : (
            <div className="state-note">
              No peer ranking — category too small or history too short.
            </div>
          )}
          {m && m.alpha_3y != null && m.beta_3y != null && (
            <div style={{ marginTop: 14, paddingTop: 10, borderTop: '1px solid var(--rule)' }}>
              <MetricRow
                k={`Alpha (3y) vs ${m.benchmark_name}`}
                v={fmtPct(m.alpha_3y)}
                cls={m.alpha_3y < 0 ? 'neg' : 'pos'}
              />
              <MetricRow k={`Beta (3y) vs ${m.benchmark_name}`} v={fmtNum(m.beta_3y)} />
              <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>
                Regressed on the oldest {m.benchmark_name} index fund as an investable
                proxy for the index, over 3 years of daily NAVs.
              </p>
            </div>
          )}
        </div>

        <div className="card full">
          <h2>Fund management</h2>
          <ManagerPanel managers={managers} />
        </div>
      </div>
    </>
  )
}
