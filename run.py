import uvicorn
import os
import sys

# Ensure package is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nse_vcp_screener.database import init_db, get_connection
from nse_vcp_screener.screener import analyze_all_stocks
from nse_vcp_screener.seed_live_data import fetch_and_seed_live_setups
from nse_vcp_screener.server import app

if __name__ == "__main__":
    init_db()
    conn = get_connection()
    cached = conn.execute("SELECT COUNT(*) FROM screen_cache").fetchone()[0]
    conn.close()
    if cached < 20:
        print("Seeding database with live NSE VCP and base setups...")
        fetch_and_seed_live_setups()

    print("\n=======================================================")
    print(">> NSE VCP Screener is running at: http://127.0.0.1:8000")
    print("=======================================================\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
