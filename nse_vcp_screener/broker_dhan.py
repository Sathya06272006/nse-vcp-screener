import os
import requests
import datetime
import pandas as pd
from typing import Dict, Any, List, Optional

class DhanConnector:
    """
    100% Free DhanHQ API v2 Connector for NSE equities.
    Docs: https://dhanhq.co/docs/v2/
    """
    BASE_URL = "https://api.dhan.co/v2"

    def __init__(self, client_id: Optional[str] = None, access_token: Optional[str] = None):
        self.client_id = client_id or os.getenv("DHAN_CLIENT_ID", "")
        self.access_token = access_token or os.getenv("DHAN_ACCESS_TOKEN", "")

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def is_configured(self) -> bool:
        return bool(self.client_id and self.access_token)

    def get_historical_daily(self, security_id: str, from_date: str, to_date: str) -> List[Dict[str, Any]]:
        """
        Fetches daily OHLCV bars for a stock from Dhan.
        from_date / to_date: 'YYYY-MM-DD'
        """
        if not self.is_configured():
            raise ValueError("Dhan Client ID and Access Token must be provided.")

        url = f"{self.BASE_URL}/charts/historical"
        payload = {
            "securityId": str(security_id),
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "expiryCode": 0,
            "fromDate": from_date,
            "toDate": to_date
        }
        res = requests.post(url, headers=self.headers, json=payload, timeout=10)
        res.raise_for_status()
        data = res.json()

        # Dhan returns lists of timestamps, opens, highs, lows, closes, volumes
        times = data.get("start_Time", [])
        opens = data.get("open", [])
        highs = data.get("high", [])
        lows = data.get("low", [])
        closes = data.get("close", [])
        volumes = data.get("volume", [])

        bars = []
        for i in range(len(times)):
            dt = datetime.datetime.fromtimestamp(times[i]).strftime("%Y-%m-%d")
            bars.append({
                "date": dt,
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": volumes[i],
                "turnover_cr": round((closes[i] * volumes[i]) / 1e7, 4)
            })
        return bars

    def get_live_ltp(self, security_ids: List[str]) -> Dict[str, float]:
        """Fetches instant live quotes for a batch of stocks during market hours."""
        if not self.is_configured():
            return {}
        url = f"{self.BASE_URL}/marketfeed/ltp"
        payload = {"NSE_EQ": [int(s) for s in security_ids if s.isdigit()]}
        res = requests.post(url, headers=self.headers, json=payload, timeout=5)
        res.raise_for_status()
        return res.json().get("data", {}).get("NSE_EQ", {})
