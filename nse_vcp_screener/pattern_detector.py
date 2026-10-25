import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple

def detect_base_and_vcp(df: pd.DataFrame, min_base_weeks: float = 3.0, max_base_weeks: float = 60.0) -> Optional[Dict[str, Any]]:
    """
    Analyzes recent price action to detect consolidation base, pivot level,
    volatility contraction (coil), volume dry-up, squats, and pokes.
    Expects df with technical indicators calculated, sorted by date ascending.
    """
    n = len(df)
    min_sessions = int(min_base_weeks * 5)
    max_sessions = min(int(max_base_weeks * 5), n - 5)

    if n < min_sessions + 10:
        return None

    c = df['close'].values
    h = df['high'].values
    l = df['low'].values
    v = df['volume'].values
    atr_pct = df['atr_pct'].values
    dates = df['date'].values

    current_price = c[-1]
    high_ever = df['high_ever'].values[-1]

    # Search backwards to identify the highest close (the potential pivot)
    # The base starts after the highest close formed within lookback window
    best_base = None

    for window_len in range(min_sessions, max_sessions + 1, 5):
        base_slice = df.iloc[-window_len:]
        b_c = base_slice['close'].values
        b_h = base_slice['high'].values
        b_l = base_slice['low'].values
        b_v = base_slice['volume'].values
        b_atr = base_slice['atr_pct'].values

        pivot = float(np.max(b_c))
        pivot_idx = int(np.argmax(b_c))
        
        # We want bases where the pivot didn't just occur today
        # (at least 5 sessions under the pivot for forming, or recently broken out)
        if pivot_idx >= window_len - 1 and current_price < pivot:
            continue

        base_low = float(np.min(b_l))
        if pivot <= 0:
            continue

        base_depth = round(((pivot - base_low) / pivot) * 100.0, 2)
        
        # Valid base depth is typically between 2% and 50%
        if base_depth > 55.0 or base_depth < 2.0:
            continue

        # Split base into two halves to measure contraction (Coil) and Volume dry-up (Dry)
        half_pt = window_len // 2
        h1_atr = np.mean(b_atr[:half_pt]) if half_pt > 0 else 1.0
        h2_atr = np.mean(b_atr[half_pt:]) if half_pt > 0 else 1.0
        coil = round(float(h2_atr / h1_atr) if h1_atr > 0 else 1.0, 2)

        h1_vol = np.mean(b_v[:half_pt]) if half_pt > 0 else 1.0
        h2_vol = np.mean(b_v[half_pt:]) if half_pt > 0 else 1.0
        dry = round(float(h2_vol / h1_vol) if h1_vol > 0 else 1.0, 2)

        # Quietest day depth
        median_vol = float(np.median(b_v))
        min_vol = float(np.min(b_v))
        dry_depth = round(min_vol / median_vol, 2) if median_vol > 0 else 1.0
        quiet_ago = int(window_len - 1 - np.argmin(b_v))

        # Squats: Days where high touched or exceeded pivot, but closed back below
        squats = int(np.sum((b_h >= pivot) & (b_c < pivot)))

        # Failed pokes: closed above pivot previously but closed back under
        pokes_n = 0
        for i in range(window_len - 1):
            if b_c[i] >= pivot and b_c[i+1] < pivot:
                pokes_n += 1

        # Up-day vs Down-day Volume & OBV
        up_mask = np.zeros(window_len, dtype=bool)
        for i in range(1, window_len):
            up_mask[i] = b_c[i] >= b_c[i-1]
            
        up_vol = float(np.sum(b_v[up_mask]))
        down_vol = float(np.sum(b_v[~up_mask]))
        ud_base = round(up_vol / down_vol, 2) if down_vol > 0 else 2.0
        obv = round((up_vol - down_vol) / (up_vol + down_vol), 2) if (up_vol + down_vol) > 0 else 0.0

        # Extension from pivot
        distpiv = round(abs(((current_price / pivot) - 1.0) * 100.0), 2)
        ext = round(((current_price / pivot) - 1.0) * 100.0, 2)

        # Structure Level (1 = ATH, 2 = within 15% of ATH, 3 = within 30%, 4 = below)
        from_ath = ((pivot / high_ever) - 1.0) * 100.0
        if from_ath >= -3.0:
            level = 1
        elif from_ath >= -15.0:
            level = 2
        elif from_ath >= -30.0:
            level = 3
        else:
            level = 4

        base_wk = round(window_len / 5.0, 1)

        best_base = {
            "pivot": round(pivot, 2),
            "baseLow": round(base_low, 2),
            "baseDepth": base_depth,
            "baseWk": base_wk,
            "baseStart": dates[-window_len],
            "ext": ext,
            "distpiv": distpiv,
            "coil": coil,
            "dry": dry,
            "dryDepth": dry_depth,
            "quietAgo": quiet_ago,
            "squats": squats,
            "pokesN": pokes_n,
            "udBase": ud_base,
            "obv": obv,
            "level": level,
            "lvl": level,
            "overhead": round(max(0.0, -from_ath), 1)
        }
        break # Select tightest confirmed consolidation

    return best_base
