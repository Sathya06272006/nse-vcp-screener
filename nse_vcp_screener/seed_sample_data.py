import os
import yfinance as yf
import pandas as pd
import datetime
from .database import init_db, get_connection
from .bhavcopy import download_equity_master
from .screener import analyze_all_stocks

SAMPLE_NSE_STOCKS = [
    # Top momentum & VCP pattern leaders on NSE
    "TRENT", "BEL", "HAL", "VBL", "DIXON", "SUZLON", "TATAELXSI", 
    "MOTHERSON", "KAYNES", "PERSISTENT", "BSOFT", "CDSL", "MCX", 
    "ZOMATO", "COFORGE", "KPITTECH", "MAZDOCK", "POLYCAB", "KEI", 
    "RVNL", "IRFC", "TITAGARH", "BHARTIARTL", "BSE", "PRESTIGE",
    "COCHINSHIP", "HUDCO", "NBCC", "JSWENERGY", "TATAINVEST",
    "APOLLOHOSP", "BHARATFORG", "SOLARINDS", "ASTRAL", "SUPREMEIND",
    "MAXHEALTH", "FORTIS", "POLICYBZR", "NYKAA", "PAYTM",
    "FEDERALBNK", "IDFCFIRSTB", "CHAMBLFERT", "DEEPAKFERT", "FACT",
    "HBLPOWER", "KEC", "ELECON", "GRSE", "BEML"
]

def seed_sample_universe(symbols=SAMPLE_NSE_STOCKS, period="1y"):
    """
    Seeds local database with historical OHLCV data for representative
    liquid NSE market leaders using yfinance for fast backfill.
    """
    print("1. Initializing SQLite Database...")
    init_db()
    conn = get_connection()

    print("2. Downloading NSE Equity Master (EQUITY_L.csv)...")
    try:
        count = download_equity_master(conn)
        print(f"   Indexed {count} NSE equities into master list.")
    except Exception as e:
        print(f"   Warning: Could not fetch EQUITY_L directly: {e}")

    print(f"3. Downloading {period} historical daily data for {len(symbols)} NSE stocks...")
    yf_symbols = [f"{s}.NS" for s in symbols]
    
    # Download in bulk
    data = yf.download(yf_symbols, period=period, interval="1d", group_by="ticker", threads=True, progress=False)
    
    records = []
    for s in symbols:
        ticker = f"{s}.NS"
        try:
            if ticker in data.columns.levels[0]:
                df = data[ticker].dropna()
                for idx, row in df.iterrows():
                    date_str = idx.strftime("%Y-%m-%d")
                    o = round(float(row['Open']), 2)
                    h = round(float(row['High']), 2)
                    l = round(float(row['Low']), 2)
                    c = round(float(row['Close']), 2)
                    v = int(row['Volume'])
                    turn_cr = round((c * v) / 1e7, 2) # approx ₹ cr
                    records.append((s, date_str, o, h, l, c, v, turn_cr, 0, 0.0))
        except Exception as e:
            continue

    print(f"   Inserting {len(records)} daily bar records...")
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
                turnover_cr=excluded.turnover_cr;
        """, records)
        
        # Ensure symbols are in stocks table
        for s in symbols:
            conn.execute("""
                INSERT OR IGNORE INTO stocks (symbol, name, series, isin)
                VALUES (?, ?, 'EQ', ?)
            """, (s, s, f"INE_{s}"))

    conn.close()

    print("4. Executing Quantitative Pattern & VCP Detection Engine...")
    results = analyze_all_stocks()
    print(f"   Pattern recognition complete! Found {len(results)} base patterns across universe.")

if __name__ == "__main__":
    seed_sample_universe()
