import json
import pandas as pd

with open("data/transactions.json") as f:
    transactions = json.load(f)

with open("data/accounts.json") as f:
    accounts = json.load(f)

df_transactions = pd.json_normalize(transactions)
df_accounts = pd.json_normalize(accounts)

with pd.ExcelWriter("data/rho_data.xlsx") as writer:
    df_transactions.to_excel(writer, sheet_name="Transactions", index=False)
    df_accounts.to_excel(writer, sheet_name="Accounts", index=False)

print("Saved to data/rho_data.xlsx")
