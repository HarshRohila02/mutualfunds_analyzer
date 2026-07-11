import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, fmtPct, fmtNum, type FundSummary } from '../api'

function scoreClass(score: number | null): string {
  if (score == null) return 'muted'
  return score >= 50 ? 'pos' : 'neg'
}

function FundTable({ funds }: { funds: FundSummary[] }) {
  const navigate = useNavigate()
  if (funds.length === 0) return null
  return (
    <table className="fund-table">
      <thead>
        <tr>
          <th>Scheme</th>
          <th style={{ textAlign: 'right' }}>Score</th>
          <th style={{ textAlign: 'right' }}>3y CAGR</th>
          <th style={{ textAlign: 'right' }}>Sharpe (3y)</th>
        </tr>
      </thead>
      <tbody>
        {funds.map((f) => (
          <tr key={f.scheme_code} onClick={() => navigate(`/fund/${f.scheme_code}`)}>
            <td className="name">
              {f.scheme_name}
              <span className="sub">
                {f.fund_house ?? '—'} · {f.category ?? 'Uncategorised'}
              </span>
            </td>
            <td className="num">
              <span className={`score-chip ${scoreClass(f.fund_score)}`}>
                {f.fund_score == null ? '—' : f.fund_score.toFixed(1)}
              </span>
            </td>
            <td className={`num ${f.cagr_3y != null && f.cagr_3y < 0 ? 'neg' : ''}`}>
              {fmtPct(f.cagr_3y)}
            </td>
            <td className="num">{fmtNum(f.sharpe_3y)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const [input, setInput] = useState(q)
  const [results, setResults] = useState<FundSummary[] | null>(null)
  const [top, setTop] = useState<FundSummary[]>([])
  const [categories, setCategories] = useState<{ category: string; scheme_count: number }[]>([])
  const [activeCat, setActiveCat] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Top categories worth surfacing as one-click filters.
  const catButtons = useMemo(
    () =>
      categories
        .filter((c) => c.category.startsWith('Equity') || c.category.startsWith('Hybrid'))
        .slice(0, 8),
    [categories],
  )

  useEffect(() => {
    api.categories().then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    api
      .topFunds(activeCat ?? undefined)
      .then(setTop)
      .catch(() => setTop([]))
  }, [activeCat])

  useEffect(() => {
    if (!q) {
      setResults(null)
      return
    }
    setBusy(true)
    setError(null)
    api
      .search(q)
      .then(setResults)
      .catch((e) => setError(String(e)))
      .finally(() => setBusy(false))
  }, [q])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setParams(input.trim() ? { q: input.trim() } : {})
  }

  return (
    <>
      <div className="search-hero">
        <p className="eyebrow">Research before rupees</p>
        <h1>Look a fund in the books before you buy it.</h1>
        <p>
          Search any of 5,000+ direct-growth schemes. Every score is computed from full NAV
          history and ranked against true category peers — the working-out is always shown.
        </p>
        <form className="search-box" onSubmit={submit}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Search by fund name — try “Parag Parikh Flexi Cap”"
            aria-label="Search funds"
          />
          <button type="submit">Search</button>
        </form>
      </div>

      {busy && <div className="state-note">Searching…</div>}
      {error && <div className="state-note error">Search failed: {error}</div>}
      {results && !busy && (
        <>
          <div className="section-head">
            <h2>
              {results.length} result{results.length === 1 ? '' : 's'} for “{q}”
            </h2>
          </div>
          {results.length > 0 ? (
            <FundTable funds={results} />
          ) : (
            <div className="state-note">
              Nothing matched. Only direct-growth plans are indexed — try the fund house name
              alone.
            </div>
          )}
        </>
      )}

      {!results && !busy && (
        <>
          <div className="section-head">
            <h2>Highest scored{activeCat ? ` — ${activeCat.replace('Scheme - ', '')}` : ''}</h2>
            <span className="muted" style={{ fontSize: 13 }}>
              category-relative composite, 0–100
            </span>
          </div>
          <div className="cat-strip">
            <button className={activeCat == null ? 'on' : ''} onClick={() => setActiveCat(null)}>
              All
            </button>
            {catButtons.map((c) => (
              <button
                key={c.category}
                className={activeCat === c.category ? 'on' : ''}
                onClick={() => setActiveCat(c.category)}
              >
                {c.category.replace('Equity Scheme - ', '').replace('Hybrid Scheme - ', '')}
              </button>
            ))}
          </div>
          <FundTable funds={top} />
        </>
      )}
    </>
  )
}
