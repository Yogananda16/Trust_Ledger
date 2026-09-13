import os
import requests
from dotenv import load_dotenv
from pipeline.rag import get_matching_patterns

load_dotenv(override=True)


def get_verdict(vendor_name: str, detail: str, tavily_findings: list = None) -> dict:
    rag_matches = get_matching_patterns(vendor_name, detail)
    tavily_text = (
        "\n".join(f"- {f['content']}" for f in (tavily_findings or []))
        or "No web results available yet."
    )

    prompt = f"""You are a fraud-risk analyst reviewing a vendor payment.

Vendor: {vendor_name}
Transaction detail: {detail}

Known fraud patterns that may apply:
{chr(10).join(f"- {p}" for p in rag_matches)}

Live web search findings about this vendor:
{tavily_text}

Respond in EXACTLY this format:
RISK: <Low, Medium, or High>
REASON: <one sentence citing specific evidence above>
"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"]

    risk, reason = "Medium", text.strip()
    for line in text.splitlines():
        if line.startswith("RISK:"):
            risk = line.replace("RISK:", "").strip()
        if line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()

    return {"risk": risk, "reason": reason, "rag_matches": rag_matches}
