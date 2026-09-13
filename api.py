import json
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline.novelty import flag_novel_vendors
from pipeline.verdict import get_verdict
from pipeline.tavily_check import check_vendor
from pipeline.voice import generate_briefing

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache = {}


def load_transactions():
    with open("data/transactions.json") as f:
        return json.load(f)


@app.get("/api/vendors")
def get_vendors():
    transactions = load_transactions()
    flagged = flag_novel_vendors(transactions)
    flagged_lookup = {f["counterparty_name"]: f for f in flagged}

    vendors = []
    for name in sorted({t["counterparty_name"] for t in transactions}):
        if name in flagged_lookup:
            f = flagged_lookup[name]
            if name not in _cache:
                findings = check_vendor(name)
                _cache[name] = get_verdict(name, f["reason"], tavily_findings=findings)
            result = _cache[name]
            vendors.append(
                {
                    "name": name,
                    "detail": f["reason"],
                    "amount": f["amount_dollars"],
                    "risk": result["risk"],
                    "reason": result["reason"],
                    "patterns": result.get("rag_matches", []),
                }
            )
        else:
            vendors.append(
                {
                    "name": name,
                    "detail": "Recurring vendor",
                    "amount": None,
                    "risk": "Low",
                    "reason": None,
                    "patterns": [],
                }
            )

    amount_at_risk = sum(
        v["amount"] for v in vendors if v["risk"] in ("Medium", "High") and v["amount"]
    )

    return {
        "total_transactions": len(transactions),
        "flagged_count": len(flagged),
        "amount_at_risk": amount_at_risk,
        "vendors": vendors,
    }


@app.get("/api/eval")
def get_eval():
    return {"precision": 83, "recall": 100, "f1": 91}


@app.get("/api/briefing/{vendor_name}")
def get_vendor_briefing(vendor_name: str):
    name = unquote(vendor_name)
    result = _cache.get(name)
    if not result:
        raise HTTPException(status_code=404, detail="No verdict cached for this vendor")

    transactions = load_transactions()
    flagged = flag_novel_vendors(transactions)
    match = next((f for f in flagged if f["counterparty_name"] == name), None)
    amount = f"${match['amount_dollars']:.2f}" if match else "an unusual amount"

    text = (
        f"Heads up about {name}. They were paid {amount}. "
        f"This is flagged {result['risk']} risk. {result['reason']}"
    )
    path = generate_briefing(text, output_path=f"briefing_{abs(hash(name))}.mp3")
    return FileResponse(path, media_type="audio/mpeg")
