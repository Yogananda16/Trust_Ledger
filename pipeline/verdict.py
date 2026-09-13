import os
import re
import threading
import time

import requests
from dotenv import load_dotenv
from pipeline.rag import get_matching_patterns

load_dotenv(override=True)

# Groq's free tier allows 8,000 tokens per minute; one verdict uses roughly 1,500.
MIN_TOKENS_BEFORE_CALL = 2_500
MAX_WAIT_SECONDS = 180

# One Groq call at a time, even when several requests hit the API together.
_groq_lock = threading.Lock()
_tokens_left = None
_tokens_reset_at = 0.0


def _seconds(duration):
    # Groq reports resets like "51.07s", "1m2.5s" or "250ms".
    match = re.fullmatch(r"(?:(\d+)m(?!s))?(?:([\d.]+)(ms|s))?", duration or "")
    if not match:
        return 10.0
    minutes, value, unit = match.groups()
    seconds = float(value or 0) / (1000 if unit == "ms" else 1)
    return int(minutes or 0) * 60 + seconds


def _ask_groq(prompt):
    global _tokens_left, _tokens_reset_at
    with _groq_lock:
        deadline = time.time() + MAX_WAIT_SECONDS
        while True:
            # Pace ourselves: if the last response said the minute's budget is nearly spent, wait it out.
            if _tokens_left is not None and _tokens_left < MIN_TOKENS_BEFORE_CALL:
                time.sleep(max(0.0, _tokens_reset_at - time.time()) + 0.5)
                _tokens_left = None

            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    # Low effort cuts hidden reasoning tokens roughly 6x for this simple format.
                    "reasoning_effort": "low",
                    "max_completion_tokens": 400,
                },
            )

            remaining = response.headers.get("x-ratelimit-remaining-tokens")
            if remaining is not None:
                _tokens_left = int(remaining)
                _tokens_reset_at = time.time() + _seconds(response.headers.get("x-ratelimit-reset-tokens"))

            if response.status_code != 429:
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]

            wait = float(response.headers.get("retry-after", 10)) + 1
            if time.time() + wait > deadline:
                response.raise_for_status()
            time.sleep(wait)


def get_verdict(vendor_name: str, detail: str, tavily_findings: list = None) -> dict:
    rag_matches = get_matching_patterns(vendor_name, detail)
    # Trimmed so each prompt stays well under Groq's per-minute token limit.
    tavily_text = (
        "\n".join(f"- {f['content'][:400]}" for f in (tavily_findings or [])[:4])
        or "No web results available yet."
    )

    prompt = f"""You are a fraud-risk analyst reviewing a vendor payment.

Vendor: {vendor_name}
Transaction detail: {detail}

Assess risk using both the evidence below and the payment amount.

A first-time payment is normal — companies hire new vendors constantly.
Treat it as a reason to verify, not as proof of fraud.

Guidance on tiers:
- High: real corroborating red flags — no findable business, a domain
  registered within months, complaints or scam reports, a name closely
  mimicking an established company, an invoice number already used by
  a different vendor, bank details that changed since earlier payments, a
  name nearly identical to a vendor already paid, pressure language with
  several new payees paid at once, or repeated payments just under the
  approval limit to a payee sharing an employee's name.
- Medium: the vendor is plausible but unverified — thin or ambiguous web
  presence, generic company name, or a large first-time payment (over
  $5,000) where a mistake would be costly to recover. A large wire with a
  vague memo is at least Medium.
- Low: the vendor is clearly an established, findable business with no
  concerning signals, or the amount is small enough that the downside is
  limited.

Do not return Low purely because nothing negative was found — absence of
evidence at a large amount is itself a reason for Medium.

Known fraud patterns that may apply:
{chr(10).join(f"- {p}" for p in rag_matches)}

Live web search findings about this vendor:
{tavily_text}

Only use web findings that clearly refer to this exact vendor name or its
domain. Ignore results about companies with similar or partial names.
Prefer the evidence from company records when citing a reason.

Respond in EXACTLY this format:
RISK: <Low, Medium, or High>
REASON: <one sentence citing specific evidence above>
"""

    text = _ask_groq(prompt)

    risk, reason = "Medium", text.strip()
    for line in text.splitlines():
        if line.startswith("RISK:"):
            risk = line.replace("RISK:", "").strip()
        if line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()

    return {"risk": risk, "reason": reason, "rag_matches": rag_matches}
