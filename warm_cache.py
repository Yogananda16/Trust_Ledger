"""Fill data/verdict_cache.json before a demo so the dashboard loads instantly.

Stop the API server first: it keeps its own copy of the cache in memory.
"""
from api import get_vendors

if __name__ == "__main__":
    vendors = [v for v in get_vendors()["vendors"] if v["reason"]]
    pending = [v["name"] for v in vendors if "rate limit" in v["reason"]]
    print(f"{len(vendors) - len(pending)} of {len(vendors)} flagged vendors have an AI verdict.")
    if pending:
        print("Still pending (run again in a minute):", ", ".join(pending))
