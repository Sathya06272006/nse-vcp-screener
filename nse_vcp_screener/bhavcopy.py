import requests
import io
import csv
import datetime
import sqlite3
import pandas as pd
from typing import Optional, List
from .database import get_connection

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def download_equity_master(db_conn: Optional[sqlite3.Connection] = None) -> int:
    """Downloads official NSE EQUITY_L.csv and populates the stocks table."""
    url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
    res = requests.get(url, headers=NSE_HEADERS, timeout=15)
    res.raise_for_status()

    lines = res.text.strip().splitlines()
    reader = csv.DictReader(lines)
    
    conn = db_conn or get_connection()
    count = 0
    records = []
    for row in reader:
        sym = row.get("SYMBOL", "").strip()
        series = row.get(" SERIES", row.get("SERIES", "")).strip()
        name = row.get("NAME OF COMPANY", "").strip()
        isin = row.get(" ISIN NUMBER", row.get("ISIN NUMBER", "")).strip()
        listing_date = row.get(" DATE OF LISTING", row.get("DATE OF LISTING", "")).strip()
        
        if series in ("EQ", "BE") and sym:
            records.append((sym, name, series, isin, listing_date))
            count += 1
            
    with conn:
        conn.executemany("""
            INSERT INTO stocks (symbol, name, series, isin, listing_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                name=excluded.name,
                series=excluded.series,
                isin=excluded.isin,
                listing_date=excluded.listing_date;
        """, records)
        
    if not db_conn:
        conn.close()
    return count

def parse_nse_date(date_str: str) -> str:
    """Converts 23-Oct-2026 or 23-OCT-2026 to 2026-10-23."""
    date_str = date_str.strip()
    try:
        dt = datetime.datetime.strptime(date_str, "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return date_str

def download_daily_bhavcopy(date: datetime.date, db_conn: Optional[sqlite3.Connection] = None) -> int:
    """
    Downloads free EOD Bhavcopy from NSE archives:
    sec_bhavdata_full_DDMMYYYY.csv
    """
    date_str = date.strftime("%d%m%Y")
    url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"
    
    try:
        res = requests.get(url, headers=NSE_HEADERS, timeout=15)
        if res.status_code == 404:
            return 0
        res.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch Bhavcopy for {date}: {e}")
        return 0

    lines = res.text.strip().splitlines()
    if not lines or len(lines) < 2:
        return 0
        
    reader = csv.DictReader(lines)
    records = []
    
    for row in reader:
        # Strip all whitespace from keys and values
        clean_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
        sym = clean_row.get("SYMBOL", "")
        series = clean_row.get("SERIES", "")
        
        if series not in ("EQ", "BE") or not sym:
            continue
            
        raw_date = clean_row.get("DATE1", "")
        formatted_date = parse_nse_date(raw_date)
        
        try:
            o = float(clean_row.get("OPEN_PRICE", 0) or 0)
            h = float(clean_row.get("HIGH_PRICE", 0) or 0)
            l = float(clean_row.get("LOW_PRICE", 0) or 0)
            c = float(clean_row.get("CLOSE_PRICE", 0) or 0)
            vol = int(clean_row.get("TTL_TRD_QNTY", 0) or 0)
            turn_lacs = float(clean_row.get("TURNOVER_LACS", 0) or 0)
            turn_cr = round(turn_lacs * 0.01, 4)
            deliv_qty = int(clean_row.get("DELIV_QTY", 0) or 0)
            deliv_pct = float(clean_row.get("DELIV_PER", 0) or 0)
            
            records.append((sym, formatted_date, o, h, l, c, vol, turn_cr, deliv_qty, deliv_pct))
        except (ValueError, TypeError):
            continue

    if not records:
        return 0

    conn = db_conn or get_connection()
    with conn:
        conn.executemany("""
            INSERT INTO daily_prices (symbol, date, open, high, low, close, volume, turnover_cr, delivery_qty, delivery_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume,
                turnover_cr=excluded.turnover_cr,
                delivery_qty=excluded.delivery_qty,
                delivery_pct=excluded.delivery_pct;
        """, records)

    if not db_conn:
        conn.close()
    return len(records)

def download_index_bhavcopy(date: datetime.date, db_conn: Optional[sqlite3.Connection] = None) -> int:
    """Downloads free daily Index Bhavcopy from NSE (Nifty 50, Nifty 500, etc.)."""
    date_str = date.strftime("%d%m%Y")
    url = f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{date_str}.csv"
    
    try:
        res = requests.get(url, headers=NSE_HEADERS, timeout=15)
        if res.status_code == 404:
            return 0
        res.raise_for_status()
    except Exception as e:
        return 0

    lines = res.text.strip().splitlines()
    if not lines or len(lines) < 2:
        return 0

    reader = csv.DictReader(lines)
    records = []
    
    for row in reader:
        clean_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
        idx_name = clean_row.get("Index Name", "")
        raw_date = clean_row.get("Index Date", "")
        formatted_date = parse_nse_date(raw_date)
        
        try:
            o = float(clean_row.get("Open Index Value", 0) or 0)
            h = float(clean_row.get("High Index Value", 0) or 0)
            l = float(clean_row.get("Low Index Value", 0) or 0)
            c = float(clean_row.get("Closing Index Value", 0) or 0)
            vol = int(float(clean_row.get("Volume", 0) or 0))
            turn_cr = float(clean_row.get("Turnover (Rs. Cr.)", 0) or 0)
            records.append((idx_name, formatted_date, o, h, l, c, vol, turn_cr))
        except (ValueError, TypeError):
            continue

    if not records:
        return 0

    conn = db_conn or get_connection()
    with conn:
        conn.executemany("""
            INSERT INTO index_prices (index_name, date, open, high, low, close, volume, turnover_cr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(index_name, date) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume,
                turnover_cr=excluded.turnover_cr;
        """, records)

    if not db_conn:
        conn.close()
    return len(records)
