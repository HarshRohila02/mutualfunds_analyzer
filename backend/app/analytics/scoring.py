"""Category-relative composite Fund Score.

Every metric is converted to a percentile rank within the scheme's own
category (mid-caps vs mid-caps, gilt vs gilt), then blended with explicit
weights. The full percentile breakdown is stored alongside the composite so
the UI/assistant can always show *why* a fund scored what it did.
"""

from __future__ import annotations

import pandas as pd

# Weights: risk-adjusted return quality dominates; raw trailing return gets
# the smallest voice since it's the noisiest / most-chased number.
SCORE_WEIGHTS = {
    "pct_sharpe_3y": 0.30,
    "pct_sortino_3y": 0.20,
    "pct_cagr_3y": 0.15,
    "pct_max_drawdown": 0.15,  # percentile of (less-negative) drawdown
    "pct_consistency": 0.20,  # rolling-3y positive share
}

# Below this many peers, a percentile rank is mostly noise.
MIN_PEERS = 5


def add_category_percentiles(df: pd.DataFrame) -> pd.DataFrame:
    """df: one row per scheme with columns [scheme_code, category, cagr_3y,
    sharpe_3y, sortino_3y, max_drawdown, rolling_3y_positive_pct].
    Returns df with pct_* columns + fund_score added.
    """
    df = df.copy()
    source_cols = {
        "pct_cagr_3y": "cagr_3y",
        "pct_sharpe_3y": "sharpe_3y",
        "pct_sortino_3y": "sortino_3y",
        "pct_max_drawdown": "max_drawdown",  # less negative = better, rank ascending works
        "pct_consistency": "rolling_3y_positive_pct",
    }

    for pct_col in source_cols:
        df[pct_col] = None
    df["fund_score"] = None
    df["category_peer_count"] = None

    for category, group in df.groupby("category", dropna=True):
        peer_count = len(group)
        df.loc[group.index, "category_peer_count"] = peer_count
        if peer_count < MIN_PEERS:
            continue
        for pct_col, src_col in source_cols.items():
            ranked = group[src_col].rank(pct=True) * 100  # NaNs stay NaN
            df.loc[group.index, pct_col] = ranked

    # Composite: weighted mean over available percentiles, re-normalizing
    # weights when a metric is missing so young-ish funds still get a score
    # from what we *can* measure (peer count already gates reliability).
    def _composite(row: pd.Series) -> float | None:
        total_weight = 0.0
        acc = 0.0
        for col, weight in SCORE_WEIGHTS.items():
            val = row[col]
            if pd.notna(val):
                acc += float(val) * weight
                total_weight += weight
        if total_weight < 0.5:  # less than half the signal available -> no score
            return None
        return round(acc / total_weight, 1)

    df["fund_score"] = df.apply(_composite, axis=1)
    return df
