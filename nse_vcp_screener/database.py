import sqlite3
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screener.db")

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn

def init_db(db_path: str = DB_PATH):
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                series TEXT,
                isin TEXT,
                listing_date TEXT,
                mcap REAL DEFAULT 0.0
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_prices (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                turnover_cr REAL,
                delivery_qty INTEGER,
                delivery_pct REAL,
                PRIMARY KEY (symbol, date)
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_prices_sym_date 
            ON daily_prices (symbol, date);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_prices_date 
            ON daily_prices (date);
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS index_prices (
                index_name TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                turnover_cr REAL,
                PRIMARY KEY (index_name, date)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screen_cache (
                symbol TEXT PRIMARY KEY,
                date TEXT,
                metrics_json TEXT
            );
        """)
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at", DB_PATH)
