export interface FundSummary {
  scheme_code: string
  scheme_name: string
  fund_house: string | null
  category: string | null
  fund_score: number | null
  cagr_3y: number | null
  sharpe_3y: number | null
}

export interface Metrics {
  computed_at: string | null
  n_nav_points: number
  history_years: number
  cagr_1y: number | null
  cagr_3y: number | null
  cagr_5y: number | null
  cagr_10y: number | null
  ann_volatility: number | null
  max_drawdown: number | null
  sharpe_3y: number | null
  sortino_3y: number | null
  rolling_3y_windows: number
  rolling_3y_positive_pct: number | null
  rolling_3y_median_cagr: number | null
  pct_cagr_3y: number | null
  pct_sharpe_3y: number | null
  pct_sortino_3y: number | null
  pct_max_drawdown: number | null
  pct_consistency: number | null
  fund_score: number | null
  category_peer_count: number | null
  score_category: string | null
  alpha_3y: number | null
  beta_3y: number | null
  benchmark_code: string | null
  benchmark_name: string | null
}

export interface FundDetail {
  scheme_code: string
  scheme_name: string
  fund_house: string | null
  category: string | null
  sub_category: string | null
  isin_growth: string | null
  metrics: Metrics | null
}

export interface NavPoint {
  date: string
  nav: number
}

export interface AssignmentScore {
  scheme_code: string
  scheme_name: string
  category: string | null
  start_date: string
  end_date: string | null
  window_years: number | null
  tenure_cagr: number | null
  tenure_sharpe: number | null
  peer_percentile: number | null
  peer_count: number | null
  skipped_reason: string | null
  note: string | null
}

export interface ManagerScore {
  manager_id: number
  name: string
  amc: string | null
  bio: string | null
  career_start_year: number | null
  tenure_score: number | null
  performance_score: number | null
  composite: number | null
  assignments: AssignmentScore[]
  caveats: string[]
}

export interface ManagerSummary {
  manager_id: number
  name: string
  amc: string | null
  n_assignments: number
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  search: (q: string) => get<FundSummary[]>(`/api/funds/search?q=${encodeURIComponent(q)}`),
  topFunds: (category?: string) =>
    get<FundSummary[]>(`/api/funds/top${category ? `?category=${encodeURIComponent(category)}` : ''}`),
  categories: () => get<{ category: string; scheme_count: number }[]>('/api/funds/categories'),
  fund: (code: string) => get<FundDetail>(`/api/funds/${code}`),
  nav: (code: string, start?: string) =>
    get<NavPoint[]>(`/api/funds/${code}/nav${start ? `?start=${start}` : ''}`),
  managers: () => get<ManagerSummary[]>('/api/managers'),
  manager: (id: number) => get<ManagerScore>(`/api/managers/${id}`),
  managersForScheme: (code: string) => get<ManagerScore[]>(`/api/managers/by-scheme/${code}`),
}

export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : `${(v * 100).toFixed(digits)}%`

export const fmtNum = (v: number | null | undefined, digits = 2) =>
  v == null ? '—' : v.toFixed(digits)
