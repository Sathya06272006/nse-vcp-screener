import json
import sqlite3
import pandas as pd
from typing import Dict, Any, List, Optional
from .database import get_connection
from .indicators import calculate_technical_indicators, calculate_rs_ratings
from .pattern_detector import detect_base_and_vcp
from .stages import classify_stage

PRESET_SCREENS = {
    "__all__": {},
    "h:VCP": {
        "coil": [0.3, 0.9],
        "dry": [0.05, 0.9],
        "baseWk": [3, 300],
        "baseDepth": [2, 35],
        "vs50": [0, 200],
        "vs200": [0, 400],
        "nearHigh": [-30, 0],
        "aboveLow": [15, 700],
        "rs": [70, 99]
    },
    "h:Blue sky": {
        "lvl": [1, 1],
        "rs": [70, 99],
        "ext": [-20, 5]
    },
    "h:Multi-year breakouts": {
        "baseWk": [52, 300],
        "ext": [-20, 10],
        "vs200": [0, 400],
        "rs": [60, 99]
    },
    "h:IPO base": {
        "listedWk": [2, 50],
        "baseWk": [3, 300],
        "baseDepth": [2, 35],
        "vs50": [0, 200],
        "ext": [-20, 5]
    }
}

def analyze_all_stocks(db_conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """
    Runs indicators, base detection, RS calculation, and stage classification
    on all stocks currently in the database.
    """
    conn = db_conn or get_connection()
    
    # Load all stocks info
    stocks_df = pd.read_sql_query("SELECT symbol, name, isin, listing_date, mcap FROM stocks", conn)
    stock_meta = {row['symbol']: row for _, row in stocks_df.iterrows()}

    # Load daily price history
    query = """
        SELECT symbol, date, open, high, low, close, volume, turnover_cr, delivery_pct
        FROM daily_prices
        ORDER BY symbol, date ASC
    """
    prices_df = pd.read_sql_query(query, conn)
    
    if prices_df.empty:
        if not db_conn:
            conn.close()
        return []

    # Group by symbol
    stock_groups = dict(tuple(prices_df.groupby('symbol')))
    
    # 1. Calculate technical indicators for each stock
    universe_dfs = {}
    for sym, group in stock_groups.items():
        if len(group) >= 15:
            universe_dfs[sym] = calculate_technical_indicators(group)

    # 2. Calculate RS Ratings across universe
    rs_ratings = calculate_rs_ratings(universe_dfs)

    # 3. Detect Bases and Classify Stages
    results = []
    for sym, df in universe_dfs.items():
        meta = stock_meta.get(sym, {})
        base_info = detect_base_and_vcp(df)
        if not base_info:
            continue

        stage_key, stage_meta = classify_stage(df, base_info)
        last_row = df.iloc[-1]
        
        # Calculate listing age in weeks
        listed_wk = 150.0 # Default established
        raw_list_date = meta.get('listing_date')
        if raw_list_date:
            try:
                ld = pd.to_datetime(raw_list_date)
                today = pd.to_datetime(last_row['date'])
                listed_wk = round((today - ld).days / 7.0, 1)
            except Exception:
                pass

        stock_result = {
            "sym": sym,
            "name": meta.get('name', sym),
            "isin": meta.get('isin', ''),
            "price": round(float(last_row['close']), 2),
            "gain": round(float(((last_row['close'] / df.iloc[-2]['close']) - 1.0) * 100.0), 2) if len(df) > 1 else 0.0,
            "turn": round(float(last_row['turn_20_median']), 2) if 'turn_20_median' in last_row else 1.0,
            "mcap": round(float(meta.get('mcap') or (last_row['close'] * last_row['volume'] * 0.001)), 2),
            "rs": rs_ratings.get(sym, 50),
            "dma50": round(float(last_row['dma50']), 2),
            "dma150": round(float(last_row['dma150']), 2),
            "dma200": round(float(last_row['dma200']), 2),
            "vs50": round(float(last_row['vs50']), 2),
            "vs200": round(float(last_row['vs200']), 2),
            "ma150over200": round(float(last_row['ma150over200']), 4) if pd.notna(last_row['ma150over200']) else 1.0,
            "trend50": round(float(last_row['trend50']), 4) if pd.notna(last_row['trend50']) else 1.0,
            "nearHigh": round(float(last_row['nearHigh']), 2),
            "aboveLow": round(float(last_row['aboveLow']), 2),
            "listedWk": listed_wk,
            "verdict": stage_key,
            **base_info,
            **(stage_meta or {})
        }
        results.append(stock_result)

    # Save to screen_cache in DB
    with conn:
        conn.execute("DELETE FROM screen_cache")
        cache_records = [(r['sym'], r.get('baseStart', ''), json.dumps(r)) for r in results]
        conn.executemany("INSERT INTO screen_cache (symbol, date, metrics_json) VALUES (?, ?, ?)", cache_records)

    if not db_conn:
        conn.close()
        
    return results

def normalize_stock_keys(s: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures consistent alias resolution across BananaPatterns and native keys."""
    norm = dict(s)
    if norm.get('nearHigh') is None and norm.get('fromHigh') is not None:
        norm['nearHigh'] = norm['fromHigh']
    if norm.get('fromHigh') is None and norm.get('nearHigh') is not None:
        norm['fromHigh'] = norm['nearHigh']
    if norm.get('lvl') is None and norm.get('level') is not None:
        norm['lvl'] = norm['level']
    if norm.get('level') is None and norm.get('lvl') is not None:
        norm['level'] = norm['lvl']
    if norm.get('distpiv') is None and norm.get('ext') is not None:
        norm['distpiv'] = abs(norm['ext'])
    return norm

def evaluate_filters(stocks: List[Dict[str, Any]], spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filters stocks by comparing against range specs [min, max]."""
    filtered = []
    for s_raw in stocks:
        s = normalize_stock_keys(s_raw)
        matches = True
        for k, v in spec.items():
            if k in ("stage", "where", "exit", "lens"):
                continue
            if isinstance(v, (list, tuple)) and len(v) == 2:
                lo, hi = v[0], v[1]
                val = s.get(k)
                if val is None:
                    matches = False
                    break
                if lo is not None and val < lo:
                    matches = False
                    break
                if hi is not None and val > hi:
                    matches = False
                    break
        if matches:
            filtered.append(s)
    return filtered

def run_screen(sel: str = "h:VCP", custom_spec: Optional[Dict[str, Any]] = None, pages: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executes screen and partitions into the 4 stages:
    'p-k-watch' (Forming)
    'p-k-trig'  (Breakout)
    'p-k-hold'  (Climbing)
    'p-k-exit'  (Played Out)
    """
    conn = get_connection()
    rows = conn.execute("SELECT metrics_json FROM screen_cache").fetchall()
    conn.close()

    if not rows:
        # Compute if cache empty
        all_stocks = analyze_all_stocks()
    else:
        all_stocks = [json.loads(r[0]) for r in rows]

    spec = PRESET_SCREENS.get(sel, {}) if not custom_spec else custom_spec
    filtered = evaluate_filters(all_stocks, spec)

    # Partition by stage
    stages = {
        "p-k-watch": [s for s in filtered if s.get('verdict') == "watch"],
        "p-k-trig":  [s for s in filtered if s.get('verdict') == "breakout"],
        "p-k-hold":  [s for s in filtered if s.get('verdict') == "running"],
        "p-k-exit":  [s for s in filtered if s.get('verdict') == "exited"]
    }

    # Sorting
    # Forming sorted by RS desc
    stages["p-k-watch"].sort(key=lambda x: x.get('rs', 0), reverse=True)
    # Breakout sorted by boVolX desc
    stages["p-k-trig"].sort(key=lambda x: x.get('boVolX', 0), reverse=True)
    # Climbing sorted by ext desc
    stages["p-k-hold"].sort(key=lambda x: x.get('ext', 0), reverse=True)
    # Exited sorted by exitDate desc
    stages["p-k-exit"].sort(key=lambda x: str(x.get('exitDate', '')), reverse=True)

    pages = pages or {}
    paginated_stages = {}
    pool = {}

    for k, rows_list in stages.items():
        pool[k] = [[s['isin'], s['sym']] for s in rows_list]
        page_info = pages.get(k, {"page": 0, "size": 40})
        p = page_info.get("page", 0)
        sz = page_info.get("size", 40)
        start = p * sz
        end = start + sz
        paginated_stages[k] = {
            "page": p,
            "size": sz,
            "total": len(rows_list),
            "rows": rows_list[start:end]
        }

    return {
        "ok": True,
        "sel": sel,
        "pool": pool,
        "counts": [
            len(stages["p-k-watch"]),
            len(stages["p-k-trig"]),
            len(stages["p-k-hold"]),
            len(stages["p-k-exit"])
        ],
        "stages": paginated_stages
    }
