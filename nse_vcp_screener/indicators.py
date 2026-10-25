import pandas as pd
import numpy as np
from typing import Dict, Any, List

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes moving averages, ATR, and volume statistics for a single stock DataFrame.
    Expects df sorted by date ascending with columns:
    ['date', 'open', 'high', 'low', 'close', 'volume', 'turnover_cr']
    """
    if len(df) < 5:
        return df

    df = df.copy()
    c = df['close']
    h = df['high']
    l = df['low']
    v = df['volume']

    # Moving Averages (DMA)
    for p in [10, 20, 50, 100, 150, 200]:
        df[f'dma{p}'] = c.rolling(p, min_periods=1).mean()
        df[f'ema{p}'] = c.ewm(span=p, adjust=False).mean()

    # Price vs Moving Averages (%)
    df['vs50'] = ((c / df['dma50']) - 1.0) * 100.0
    df['vs200'] = ((c / df['dma200']) - 1.0) * 100.0
    df['ma150over200'] = df['dma150'] / df['dma200'].replace(0, np.nan)
    df['trend50'] = df['dma50'] / df['dma200'].replace(0, np.nan)

    # True Range & ATR
    prev_c = c.shift(1).fillna(c)
    tr1 = h - l
    tr2 = (h - prev_c).abs()
    tr3 = (l - prev_c).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['tr'] = tr
    df['atr14'] = tr.rolling(14, min_periods=1).mean()
    df['atr_pct'] = (df['atr14'] / c.replace(0, np.nan)) * 100.0

    # Volume & Turnover Statistics
    df['vol_20_median'] = v.rolling(20, min_periods=1).median().replace(0, np.nan)
    df['rvol1d'] = (v / df['vol_20_median']).round(2)
    df['turn_20_median'] = df['turnover_cr'].rolling(20, min_periods=1).median().round(2)

    # 52-Week (252 sessions) High / Low
    df['high_1y'] = c.rolling(252, min_periods=1).max()
    df['low_1y'] = c.rolling(252, min_periods=1).min()
    df['nearHigh'] = ((c / df['high_1y']) - 1.0) * 100.0 # 0% is at high, negative below
    df['aboveLow'] = ((c / df['low_1y']) - 1.0) * 100.0

    # All-Time High
    df['high_ever'] = c.cummax()
    df['fromEver'] = ((c / df['high_ever']) - 1.0) * 100.0

    return df

def calculate_rs_ratings(universe_dfs: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    """
    Computes Relative Strength Rating (1-99 percentile) across the liquid universe.
    Weighted formula: 40% (3M return) + 20% (6M return) + 20% (9M return) + 20% (12M return).
    """
    scores = {}
    for sym, df in universe_dfs.items():
        if len(df) < 60:
            continue
        c = df['close'].values
        n = len(c)
        
        # Quarter returns
        ret_3m = (c[-1] / c[-min(n, 63)]) - 1.0
        ret_6m = (c[-1] / c[-min(n, 126)]) - 1.0 if n >= 126 else ret_3m
        ret_9m = (c[-1] / c[-min(n, 189)]) - 1.0 if n >= 189 else ret_6m
        ret_12m = (c[-1] / c[-min(n, 252)]) - 1.0 if n >= 252 else ret_9m

        weighted_score = 0.4 * ret_3m + 0.2 * ret_6m + 0.2 * ret_9m + 0.2 * ret_12m
        scores[sym] = weighted_score

    if not scores:
        return {}

    # Rank into 1-99 percentiles
    series = pd.Series(scores)
    ranks = series.rank(pct=True) * 99.0
    rs_ratings = ranks.round().clip(lower=1, upper=99).astype(int).to_dict()
    return rs_ratings
