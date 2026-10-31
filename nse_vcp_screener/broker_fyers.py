import os
import requests
import datetime
from typing import Dict, Any, List, Optional

class FyersConnector:
    """
    100% Free Fyers API v3 Connector for NSE equities.
    Docs: https://myapi.fyers.in/docsv3
    """
    BASE_URL = "https://api-t1.fyers.in/data"

    def __init__(self, app_id: Optional[str] = None, access_token: Optional[str] = None):
        self.app_id = app_id or os.getenv("FYERS_APP_ID", "")
        self.access_token = access_token or os.getenv("FYERS_ACCESS_TOKEN", "")

    @property
    def auth_header(self) -> str:
        return f"{self.app_id}:{self.access_token}"

    def is_configured(self) -> bool:
        return bool(self.app_id and self.access_token)

    def get_historical_daily(self, symbol: str, range_from: str, range_to: str) -> List[Dict[str, Any]]:
        """
        Fetches daily candles for a stock.
        symbol format: 'NSE:TRENT-EQ'
        range_from / range_to: 'YYYY-MM-DD'
        """
        if not self.is_configured():
            raise ValueError("Fyers App ID and Access Token must be provided.")

        formatted_sym = symbol if symbol.startswith("NSE:") else f"NSE:{symbol}-EQ"
        url = f"{self.BASE_URL}/history"
        params = {
            "symbol": formatted_sym,
            "resolution": "D",
            "date_format": "1",
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "1"
        }
        headers = {"Authorization": self.auth_header}
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()

        candles = data.get("candles", [])
        bars = []
        for c in candles:
            # Fyers candle: [timestamp, open, high, low, close, volume]
            dt = datetime.datetime.fromtimestamp(c[0]).strftime("%Y-%m-%d")
            bars.append({
                "date": dt,
                "open": c[1],
                "high": c[2],
                "low": c[3],
                "close": c[4],
                "volume": c[5],
                "turnover_cr": round((c[4] * c[5]) / 1e7, 4)
            })
        return bars

    def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Fetches live quotes and market depth for multiple stocks."""
        if not self.is_configured():
            return {}
        formatted = [s if s.startswith("NSE:") else f"NSE:{s}-EQ" for s in symbols]
        url = f"{self.BASE_URL}/quotes"
        params = {"symbols": ",".join(formatted)}
        headers = {"Authorization": self.auth_header}
        res = requests.get(url, headers=headers, params=params, timeout=5)
        res.raise_for_status()
        return res.json().get("d", [])
