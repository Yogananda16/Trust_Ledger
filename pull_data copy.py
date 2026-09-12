import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://rhoapi-sandbox.rho.co/api/v1"
TOKEN = os.getenv("RHO_API_TOKEN")  # "sandbox"

headers = {"Authorization": f"Bearer {TOKEN}"}


def get_all(endpoint, params=None):
    """Walk every page of a Rho list endpoint and return all items."""
    params = dict(params or {})
    items = []
    while True:
        resp = requests.get(f"{BASE_URL}/{endpoint}", headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        items.extend(
            data[endpoint]
        )  # key matches the resource name, e.g. "transactions"
        next_token = data.get("page", {}).get("next_page_token")
        if not next_token:
            break
        params["page_token"] = next_token
    return items


accounts = get_all("accounts")
transactions = get_all("transactions")

if __name__ == "__main__":
    accounts = get_all("accounts")
    transactions = get_all("transactions")

    os.makedirs("data", exist_ok=True)
    with open("data/accounts.json", "w") as f:
        json.dump(accounts, f, indent=2)
    with open("data/transactions.json", "w") as f:
        json.dump(transactions, f, indent=2)

    print(
        f"Saved {len(accounts)} accounts and {len(transactions)} transactions to data/"
    )
