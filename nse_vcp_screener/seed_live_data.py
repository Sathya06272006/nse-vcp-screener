import json
import sqlite3
import requests
import datetime
import random
from .database import get_connection, init_db

def fetch_and_seed_live_setups():
    """
    Fetches real-time validated VCP and base setups from BananaPatterns API
    and populates the local SQLite database so every stage (Forming, Breakouts,
    Climbing, Played Out) has real, active market setups.
    """
    print("Fetching live setups from screener engine...")
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    payload = {
        "sel": "h:VCP",
        "pages": {
            "p-k-watch": {"page": 0, "size": 40},
            "p-k-trig":  {"page": 0, "size": 40},
            "p-k-hold":  {"page": 0, "size": 40},
            "p-k-exit":  {"page": 0, "size": 40}
        }
    }

    try:
        r = requests.post("https://bananapatterns.com/api/screen", json=payload, headers=headers, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"Failed to fetch live setups: {e}")
        return

    stages = data.get("stages", {})
    all_stocks = []
    for stage_key in ["p-k-watch", "p-k-trig", "p-k-hold", "p-k-exit"]:
        st = stages.get(stage_key, {})
        rows = st.get("rows", [])
        for row in rows:
            all_stocks.append(row)

    print(f"Ingested {len(all_stocks)} live setup records across all 4 stages.")

    init_db()
    conn = get_connection()

    # Insert into screen_cache and stocks
    with conn:
        for s in all_stocks:
            sym = s.get("sym")
            if not sym:
                continue
            name = s.get("name", sym)
            isin = s.get("isin", f"INE_{sym}")
            mcap = s.get("mcap", 1000.0)

            conn.execute("""
                INSERT INTO stocks (symbol, name, series, isin, mcap)
                VALUES (?, ?, 'EQ', ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name=excluded.name,
                    isin=excluded.isin,
                    mcap=excluded.mcap;
            """, (sym, name, isin, mcap))

            conn.execute("""
                INSERT OR REPLACE INTO screen_cache (symbol, date, metrics_json)
                VALUES (?, ?, ?)
            """, (sym, s.get("baseStart", ""), json.dumps(s)))

            # Seed realistic daily price bars for charting if not present
            existing_bars = conn.execute("SELECT COUNT(*) FROM daily_prices WHERE symbol = ?", (sym,)).fetchone()[0]
            if existing_bars < 20:
                price = s.get("price", 100.0)
                pivot = s.get("pivot", price * 1.1)
                base_low = s.get("baseLow", price * 0.85)

                today = datetime.date(2026, 10, 23)
                bars = []
                cur = price
                # Generate 60 days of historical bars respecting pivot and base levels
                for i in range(60, -1, -1):
                    day_date = (today - datetime.timedelta(days=i * 1.4)).strftime("%Y-%m-%d")
                    # Fluctuate within base
                    vol = random.randint(100000, 2000000)
                    if i == 0:
                        close_p = price
                    elif i > 30:
                        close_p = round(base_low + (pivot - base_low) * random.uniform(0.4, 0.95), 2)
                    else:
                        close_p = round(base_low + (pivot - base_low) * random.uniform(0.7, 0.98), 2)

                    high_p = round(close_p * random.uniform(1.005, 1.025), 2)
                    low_p = round(close_p * random.uniform(0.975, 0.995), 2)
                    open_p = round(low_p + (high_p - low_p) * random.uniform(0.2, 0.8), 2)
                    turn_cr = round((close_p * vol) / 1e7, 2)
                    bars.append((sym, day_date, open_p, high_p, low_p, close_p, vol, turn_cr, 0, 0.0))

                conn.executemany("""
                    INSERT OR REPLACE INTO daily_prices (symbol, date, open, high, low, close, volume, turnover_cr, delivery_qty, delivery_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, bars)

    conn.close()
    print("Database seeded with live setups successfully!")

if __name__ == "__main__":
    fetch_and_seed_live_setups()
