import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(override=True)
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def check_vendor(vendor_name: str) -> list:
    try:
        response = client.search(
            query=f"{vendor_name} company reviews scam complaints domain registration",
            search_depth="advanced",
        )
        return [
            {"url": r["url"], "content": r["content"][:300]}
            for r in response["results"][:5]
        ]
    except Exception as e:
        print("Tavily error:", e)
        return []
