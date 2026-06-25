"""Verify FinMind token and download 5y price data for V1 tickers."""
import os, sys
from pathlib import Path

# Load .env
env_path = Path(".env")
token = ""
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.startswith("FINMIND_TOKEN="):
            token = line.split("=", 1)[1].strip()
            break
if not token:
    token = os.environ.get("FINMIND_TOKEN", "")

print(f"Token found: {bool(token)} ({token[:20]}...)" if token else "Token NOT found")

# Verify FinMind connection
from modules.finmind_client import FinMindClient
fm = FinMindClient(token=token)
print(f"FinMind has_token: {fm.has_token}")

# Quick API test - fetch stock info for 2330
try:
    import requests
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": "2330",
        "start_date": "2026-06-17",
        "end_date": "2026-06-19",
        "token": token,
    }
    r = requests.get(url, params=params, timeout=15)
    data = r.json()
    if data.get("status") == 200:
        n = len(data.get("data", []))
        print(f"FinMind API OK — 2330 institutional data: {n} rows")
    else:
        print(f"FinMind API response: {data.get('msg', data)}")
except Exception as e:
    print(f"FinMind API error: {e}")
