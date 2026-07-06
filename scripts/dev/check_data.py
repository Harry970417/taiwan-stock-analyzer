import sqlite3, pandas as pd, sys

conn = sqlite3.connect("data/stock_data.db")
tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
print(f"SQLite tables ({len(tables)}):")
for t in tables["name"].tolist():
    try:
        info = pd.read_sql(f'SELECT MIN(date) as min_d, MAX(date) as max_d, COUNT(*) as n FROM "{t}"', conn)
        print(f"  {t:45s}  {info['min_d'].iloc[0]} → {info['max_d'].iloc[0]}  ({info['n'].iloc[0]} rows)")
    except Exception as e:
        print(f"  {t}: {e}")
conn.close()

# Check FinMind token
import os
from pathlib import Path
env_path = Path(".env")
token = ""
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "FINMIND" in line.upper() and "=" in line:
            token = line.split("=", 1)[1].strip()
            break
if not token:
    token = os.environ.get("FINMIND_TOKEN", "")
print(f"\nFINMIND_TOKEN: {'PRESENT' if token else 'MISSING'}")
