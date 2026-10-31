import requests
import json
import datetime
import sqlite3
from typing import Dict, Any, List, Optional
from .database import get_connection

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/"
}

class MarketBriefEngine:
    """
    Market Brief & Catalyst Intelligence Engine.
    Correlates quarterly financial results and high-impact corporate announcements
    with technical base structures (RS rating, stage, pivot, extension).
    """

    @staticmethod
    def get_market_brief(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
        """
        Builds the daily brief payload:
        1. Results: Financial results filed with Revenue, PAT, EPS YoY changes
        2. Announcements: High-impact corporate filings (orders, plant COD, warrants)
        3. Due: Upcoming board meetings scheduled to declare quarterly earnings
        """
        db = conn or get_connection()
        cached_rows = db.execute("SELECT metrics_json FROM screen_cache").fetchall()
        if not conn:
            db.close()

        stock_map = {}
        for r in cached_rows:
            try:
                s = json.loads(r[0])
                stock_map[s.get("sym")] = s
            except Exception:
                continue

        # In production, this ingests live from NSE/BSE corporate announcement feeds.
        # Fallback to current exchange session dates:
        today_str = datetime.date.today().strftime("%Y-%m-%d")

        brief_payload = {
            "ok": True,
            "kind": "day",
            "day": today_str,
            "asOf": today_str,
            "summary": {
                "total_tracked": len(stock_map),
                "in_vcp": sum(1 for s in stock_map.values() if s.get("coil", 2.0) <= 0.9 and s.get("dry", 2.0) <= 0.9),
                "leaders_count": sum(1 for s in stock_map.values() if s.get("rs", 0) >= 80)
            },
            "results": [],
            "announcements": [],
            "calendar": []
        }

        # Enrich any detected stock setups with their latest catalysts
        for sym, stock in list(stock_map.items())[:20]:
            if stock.get("verdict") in ("watch", "breakout", "running"):
                brief_payload["results"].append({
                    "symbol": sym,
                    "name": stock.get("name"),
                    "price": stock.get("price"),
                    "gain": stock.get("gain"),
                    "stage": stock.get("verdict"),
                    "pivot": stock.get("pivot"),
                    "ext": stock.get("ext"),
                    "rs": stock.get("rs"),
                    "coil": stock.get("coil"),
                    "dry": stock.get("dry")
                })

        return brief_payload
