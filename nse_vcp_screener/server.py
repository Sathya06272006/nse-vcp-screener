import os
import json
import sqlite3
import datetime
import pandas as pd
from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from .database import get_connection
from .screener import run_screen, analyze_all_stocks, PRESET_SCREENS
from .bhavcopy import download_daily_bhavcopy

app = FastAPI(title="NSE VCP Pattern Screener", version="1.0.0")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class ScreenRequest(BaseModel):
    sel: Optional[str] = "h:VCP"
    spec: Optional[Dict[str, Any]] = None
    pages: Optional[Dict[str, Any]] = None
    lens: Optional[Dict[str, Any]] = None

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return "<h1>NSE VCP Screener</h1><p>Static files loading...</p>"

@app.post("/api/screen")
async def api_screen(req: ScreenRequest):
    """
    Evaluates screens and partitions stocks into the 4 stages:
    Forming (p-k-watch), Breakout (p-k-trig), Climbing (p-k-hold), Played Out (p-k-exit).
    Compatible with BananaPatterns frontend schema.
    """
    try:
        results = run_screen(sel=req.sel or "h:VCP", custom_spec=req.spec, pages=req.pages)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/screen_counts")
async def api_screen_counts(payload: Dict[str, Any] = Body(...)):
    """Returns stage count badges for one or multiple screens."""
    items = payload.get("items", [])
    counts_list = []
    for item in items:
        sel = item.get("sel", "h:VCP")
        spec = item.get("spec")
        res = run_screen(sel=sel, custom_spec=spec)
        counts_list.append(res.get("counts", [0, 0, 0, 0]))
    return {"ok": True, "counts": counts_list}

@app.get("/api/stocks/{symbol}")
async def api_stock_detail(symbol: str):
    """Returns detailed OHLCV series, pivot, base annotations, and indicators for chart modal."""
    conn = get_connection()
    meta_row = conn.execute("SELECT name, isin, listing_date, mcap FROM stocks WHERE symbol = ?", (symbol,)).fetchone()
    cache_row = conn.execute("SELECT metrics_json FROM screen_cache WHERE symbol = ?", (symbol,)).fetchone()
    
    prices = conn.execute("""
        SELECT date, open, high, low, close, volume, turnover_cr, delivery_pct
        FROM daily_prices
        WHERE symbol = ?
        ORDER BY date ASC
    """, (symbol,)).fetchall()
    conn.close()

    if not prices:
        raise HTTPException(status_code=404, detail=f"No price history found for symbol {symbol}")

    bars = []
    for p in prices:
        bars.append({
            "time": p[0],
            "open": p[1],
            "high": p[2],
            "low": p[3],
            "close": p[4],
            "volume": p[5],
            "turnover": p[6],
            "deliveryPct": p[7]
        })

    metrics = json.loads(cache_row[0]) if cache_row else {}
    
    return {
        "ok": True,
        "symbol": symbol,
        "name": meta_row[0] if meta_row else symbol,
        "isin": meta_row[1] if meta_row else "",
        "mcap": meta_row[3] if meta_row else 0.0,
        "metrics": metrics,
        "bars": bars
    }

@app.get("/api/market_health")
async def api_market_health():
    """Computes overall market breadth and regime across active universe."""
    conn = get_connection()
    rows = conn.execute("SELECT metrics_json FROM screen_cache").fetchall()
    conn.close()
    
    if not rows:
        return {"universe": 0, "pct_uptrend": 0, "regime": "neutral", "leaders": 0}

    stocks = [json.loads(r[0]) for r in rows]
    total = len(stocks)
    above_50 = sum(1 for s in stocks if s.get('vs50', 0) > 0)
    pct_uptrend = round((above_50 / total) * 100) if total > 0 else 0
    leaders = sum(1 for s in stocks if s.get('rs', 0) >= 80)

    regime = "Risk-On" if pct_uptrend >= 50 else "Risk-Off"

    return {
        "ok": True,
        "universe": total,
        "in_uptrend": above_50,
        "pct_uptrend": pct_uptrend,
        "leaders": leaders,
        "regime": regime
    }

@app.post("/api/sync_bhavcopy")
async def api_sync_bhavcopy(date_str: Optional[str] = None):
    """
    Downloads free NSE Bhavcopy for specified date (YYYY-MM-DD or today)
    and triggers quantitative screen re-calculation.
    """
    conn = get_connection()
    if date_str:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        dt = datetime.date.today()

    count = download_daily_bhavcopy(dt, conn)
    conn.close()

    if count > 0:
        analyze_all_stocks()
        return {"ok": True, "message": f"Successfully ingested {count} Bhavcopy records for {dt} and updated screener cache."}
    else:
        return {"ok": False, "message": f"No Bhavcopy available for {dt} (holiday or weekend)."}
