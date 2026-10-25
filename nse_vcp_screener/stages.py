import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple

def classify_stage(df: pd.DataFrame, base_info: Optional[Dict[str, Any]], stop_pct: float = 8.0) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Classifies a stock into one of the four lifecycle stages:
    'watch' (Forming)
    'breakout' (Fresh Breakout)
    'running' (Climbing)
    'exited' (Played Out)
    
    Returns (stage_key, stage_metadata)
    """
    if not base_info or len(df) < 20:
        return "none", None

    c = df['close'].values
    h = df['high'].values
    l = df['low'].values
    v = df['volume'].values
    dates = df['date'].values
    dma50 = df['dma50'].values
    vol_median = df['vol_20_median'].values

    pivot = base_info['pivot']
    current_close = c[-1]
    ext = base_info['ext']

    # 1. Forming Stage
    # Price is still below the pivot (coiling / tightening)
    if ext < 0.0:
        return "watch", {
            "verdict": "watch",
            "stage": "forming",
            "why": f"Basing in tight consolidation, {abs(ext)}% below ₹{pivot} pivot"
        }

    # If ext >= 0.0, a breakout occurred. Let's find WHEN it crossed the pivot.
    # Scan backward from today to find the first day close crossed above pivot
    bo_idx = None
    for i in range(len(c) - 1, max(0, len(c) - 60), -1):
        if c[i] >= pivot and (i == 0 or c[i-1] < pivot):
            bo_idx = i
            break

    if bo_idx is None:
        # Broke out earlier than 60 sessions ago
        bo_idx = max(0, len(c) - 40)

    since_bo = len(c) - 1 - bo_idx
    bo_date = dates[bo_idx]
    bo_close = c[bo_idx]
    bo_open = df['open'].values[bo_idx]
    bo_high = h[bo_idx]
    bo_low = l[bo_idx]
    bo_vol = v[bo_idx]
    med_vol = vol_median[bo_idx] if vol_median[bo_idx] > 0 else 1.0
    bo_vol_x = round(float(bo_vol / med_vol), 2)
    bo_range = round(float((bo_close - bo_low) / (bo_high - bo_low)), 2) if (bo_high - bo_low) > 0 else 0.5
    bo_thru = round(((bo_close / pivot) - 1.0) * 100.0, 2)
    bo_gap = round(((bo_open / pivot) - 1.0) * 100.0, 2)

    breakout_meta = {
        "boDate": bo_date,
        "boClose": bo_close,
        "boVolX": bo_vol_x,
        "boRange": bo_range,
        "boThru": bo_thru,
        "boGap": bo_gap,
        "sinceBo": since_bo,
        "pivot": pivot
    }

    # Check for Played Out / Exited condition
    # Rule 1: Fell >= 8% below pivot or breakout close
    # Rule 2: Closed below 50-DMA
    stop_level = pivot * (1.0 - stop_pct / 100.0)
    
    # Check post-breakout sessions for exit
    for i in range(bo_idx + 1, len(c)):
        day_close = c[i]
        day_date = dates[i]
        day_dma50 = dma50[i]
        
        if day_close <= stop_level:
            ret_pct = round(((day_close / pivot) - 1.0) * 100.0, 2)
            return "exited", {
                **breakout_meta,
                "verdict": "exited",
                "stage": "played",
                "exitDate": day_date,
                "retPct": ret_pct,
                "why": f"Hit −{stop_pct}% stop level at ₹{day_close:.2f}"
            }
            
        if day_dma50 > 0 and day_close < day_dma50 and (i - bo_idx) > 10:
            ret_pct = round(((day_close / pivot) - 1.0) * 100.0, 2)
            return "exited", {
                **breakout_meta,
                "verdict": "exited",
                "stage": "played",
                "exitDate": day_date,
                "retPct": ret_pct,
                "why": "Closed below trailing 50-day moving average"
            }

    # If within 5 sessions of breakout and above pivot -> Fresh Breakout
    if since_bo <= 5 and ext >= 0.0 and ext <= 8.0:
        return "breakout", {
            **breakout_meta,
            "verdict": "breakout",
            "stage": "breakout",
            "why": f"Fresh breakout through ₹{pivot} ({since_bo} days ago) on {bo_vol_x}x volume"
        }

    # Otherwise currently running / climbing
    return "running", {
        **breakout_meta,
        "verdict": "running",
        "stage": "climbing",
        "why": f"Climbing above ₹{pivot} pivot (+{ext}%), holding trend"
    }
