import json
import os
import threading
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline.evidence import build_evidence
from pipeline.novelty import flag_novel_vendors
from pipeline.verdict import get_verdict
from pipeline.tavily_check import check_vendor, check_vendor_reputation, search_pattern
from pipeline.voice import generate_briefing

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,https://trust-ledger-ai.vercel.app"
    ).split(","),
    # Vercel preview deployments get their own trust-ledger-*.vercel.app URLs.
    allow_origin_regex=r"https://trust-ledger[\w-]*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_PATH = Path("data/verdict_cache.json")

# Verdicts are saved to disk so a restart doesn't re-run every web search and LLM call.
_cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}

_verdict_lock = threading.Lock()

# Bump when the vendor-name web search changes, so old search results get refreshed.
SEARCH_VERSION = 3

# Labelled demo transactions modelled on real fraud cases. Set DEMO_SCENARIOS=0 to hide them.
SHOW_DEMO = os.getenv("DEMO_SCENARIOS", "1") != "0"


def load_playbook():
    with open("data/playbook.json", encoding="utf-8") as f:
        return json.load(f)


def load_transactions():
    with open("data/transactions.json", encoding="utf-8") as f:
        transactions = json.load(f)
    if SHOW_DEMO:
        with open("data/demo_scenarios.json", encoding="utf-8") as f:
            transactions += json.load(f)
    return transactions


def latest_flag_per_vendor(transactions):
    # Flags come back in date order, so later payments overwrite earlier ones.
    return {f["counterparty_name"]: f for f in flag_novel_vendors(transactions)}


def _save_cache():
    CACHE_PATH.write_text(json.dumps(_cache, indent=2))


def verdict_for(name, flag, detail):
    # Serialised so overlapping page loads reuse one verdict instead of each calling Groq.
    with _verdict_lock:
        cached = _cache.get(name)
        search_current = bool(cached) and cached.get("search_version") == SEARCH_VERSION
        if search_current and cached.get("detail") == detail:
            return cached

        if search_current:
            findings = cached.get("sources", [])
        elif flag.get("scenario") and not flag.get("pin"):
            # Made-up demo vendors: a name search would only find unrelated real companies.
            findings = []
        elif any("solicitation" in s["context"] for s in flag["signals"]):
            # Listing and renewal invoices are a known scam format, so look for scam records, not a company profile.
            findings = check_vendor_reputation(name) or check_vendor(name)
        else:
            findings = check_vendor(name)

        try:
            verdict = get_verdict(name, detail, tavily_findings=findings)
        except Exception as e:
            print(f"Verdict failed for {name}:", e)
            # Keep the web search so the retry only needs the LLM, and show a stand-in until then.
            _cache[name] = {"sources": findings, "search_version": SEARCH_VERSION, "detail": None}
            _save_cache()
            has_pattern = any(s["pattern"] for s in flag["signals"])
            return {
                "risk": "High" if has_pattern else "Medium",
                "reason": "AI review is paused by the rate limit, so this rating comes from the signals alone. Refresh in a minute.",
                "rag_matches": [],
                "sources": findings,
            }

        verdict.update(sources=findings, detail=detail, search_version=SEARCH_VERSION)
        _cache[name] = verdict
        _save_cache()
        return verdict


@app.get("/")
def health():
    # Hosting platforms check the root URL to see that the server is up.
    return {"status": "ok", "service": "TrustLedger API"}


@app.get("/api/vendors")
def get_vendors():
    transactions = load_transactions()
    flagged_lookup = latest_flag_per_vendor(transactions)
    playbook = {p["id"]: p for p in load_playbook()}

    vendors = []
    for name in sorted({t["counterparty_name"] for t in transactions}):
        if name in flagged_lookup:
            f = flagged_lookup[name]
            evidence = build_evidence(f, transactions)
            pattern = next((s["pattern"] for s in f["signals"] if s["pattern"] in playbook), None)
            web_evidence = (
                search_pattern(pattern, playbook[pattern]["search_query"], playbook[pattern].get("search_keywords"))
                if pattern
                else []
            )

            detail = f'{f["reason"]}. Memo: "{f["clean_memo"]}"'
            if evidence:
                detail += "\nEvidence from company records:\n" + "\n".join(f"- {e}" for e in evidence)

            result = verdict_for(name, f, detail)
            vendors.append(
                {
                    "name": name,
                    "detail": f["clean_memo"],
                    "signals": f["signals"],
                    "evidence": evidence,
                    "web_evidence": web_evidence,
                    "scenario": bool(f.get("scenario")),
                    "pin": f.get("pin"),
                    # Kept for the frontend version already live on Vercel, which sorts by this.
                    "featured": f.get("pin") is not None,
                    "amount": f["amount_dollars"],
                    "risk": result["risk"],
                    "reason": result["reason"],
                    "patterns": result.get("rag_matches", []),
                    "sources": result.get("sources", []),
                }
            )
        else:
            vendors.append(
                {
                    "name": name,
                    "detail": "Recurring vendor",
                    "signals": [],
                    "evidence": [],
                    "web_evidence": [],
                    "scenario": False,
                    "pin": None,
                    "featured": False,
                    "amount": None,
                    "risk": "Low",
                    "reason": None,
                    "patterns": [],
                    "sources": [],
                }
            )

    amount_at_risk = sum(
        v["amount"] for v in vendors if v["risk"] in ("Medium", "High") and v["amount"]
    )

    return {
        "total_transactions": len(transactions),
        "flagged_count": len(flagged_lookup),
        "amount_at_risk": amount_at_risk,
        "demo_count": sum(1 for t in transactions if t.get("scenario")),
        "vendors": vendors,
    }


@app.get("/api/playbook")
def get_playbook():
    playbook = load_playbook()
    flagged_lookup = latest_flag_per_vendor(load_transactions())
    for play in playbook:
        play["matches"] = sorted(
            name
            for name, f in flagged_lookup.items()
            if any(s["pattern"] == play["id"] for s in f["signals"])
        )
    return playbook


@app.get("/api/eval")
def get_eval():
    return {"precision": 83, "recall": 100, "f1": 91}


@app.get("/api/briefing/{vendor_name}")
def get_vendor_briefing(vendor_name: str):
    name = unquote(vendor_name)
    result = _cache.get(name)
    if not result or "risk" not in result:
        raise HTTPException(status_code=404, detail="No verdict cached for this vendor")

    match = latest_flag_per_vendor(load_transactions()).get(name)
    amount = f"${match['amount_dollars']:.2f}" if match else "an unusual amount"

    text = (
        f"Heads up about {name}. They were paid {amount}. "
        f"This is flagged {result['risk']} risk. {result['reason']}"
    )
    path = generate_briefing(text, output_path=f"briefing_{abs(hash(name))}.mp3")
    return FileResponse(path, media_type="audio/mpeg")
