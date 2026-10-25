import uvicorn
import os
import sys

# Ensure package is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nse_vcp_screener.database import init_db
from nse_vcp_screener.screener import analyze_all_stocks
from nse_vcp_screener.server import app

if __name__ == "__main__":
    init_db()
    analyze_all_stocks()
    print("\n=======================================================")
    print(">> NSE VCP Screener is running at: http://127.0.0.1:8000")
    print("=======================================================\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
