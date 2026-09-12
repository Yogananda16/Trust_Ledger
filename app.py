import streamlit as st
import json

from pipeline.novelty import flag_novel_vendors
from pipeline.verdict import get_verdict
from pipeline.voice import generate_briefing

st.set_page_config(page_title="TrustLedger", layout="wide")
st.markdown(
    "<style>#MainMenu, footer, header {visibility: hidden;}</style>",
    unsafe_allow_html=True,
)

RISK_COLORS = {
    "Low": ("#e6f4ea", "#1e7e34"),
    "Medium": ("#fff4e5", "#b26a00"),
    "High": ("#fdecea", "#c62828"),
}


def render_vendor_row(name, detail, risk, evidence=None):
    bg, fg = RISK_COLORS.get(risk, RISK_COLORS["Medium"])
    st.markdown(
        f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                padding:12px 16px;border-bottom:1px solid #eee;">
        <div>
            <p style="margin:0;font-weight:600;">{name}</p>
            <p style="margin:0;font-size:13px;color:#666;">{detail}</p>
        </div>
        <span style="background:{bg};color:{fg};font-size:12px;font-weight:600;
                     padding:4px 10px;border-radius:6px;">{risk}</span>
    </div>
    """,
        unsafe_allow_html=True,
    )
    if evidence:
        with st.expander("Why this was flagged"):
            for e in evidence:
                st.write(f"- {e}")


@st.cache_data
def cached_verdict(name, detail):
    # TODO once pipeline/tavily_check.py (Meghana's piece) is ready:
    # from pipeline.tavily_check import check_vendor
    # tavily_findings = check_vendor(name)["findings"]
    # return get_verdict(name, detail, tavily_findings=tavily_findings)
    return get_verdict(name, detail)


# ---------- Beat 1: live data ----------
st.title("TrustLedger")
with open("data/transactions.json") as f:
    transactions = json.load(f)
st.caption(f"Loaded {len(transactions)} transactions from Rho's sandbox")

# ---------- Beat 2 + 3: vendor list, real novelty + verdict ----------
st.subheader("Vendors")
flagged = flag_novel_vendors(transactions)
flagged_lookup = {f["counterparty_name"]: f for f in flagged}

for name in sorted({t["counterparty_name"] for t in transactions}):
    if name in flagged_lookup:
        f = flagged_lookup[name]
        result = cached_verdict(name, f["reason"])
        evidence = [result["reason"]] + result.get("rag_matches", [])[:1]
        render_vendor_row(name, f["reason"], result["risk"], evidence)
    else:
        render_vendor_row(name, "Recurring vendor", "Low")

# ---------- Beat 4: voice briefing ----------
st.subheader("Briefing")
if st.button("Play briefing"):
    if flagged:
        top = flagged[0]
        top_result = cached_verdict(top["counterparty_name"], top["reason"])
        briefing_text = (
            f"Heads up. {top['counterparty_name']} was just paid "
            f"${top['amount_dollars']:.2f}. Risk level: {top_result['risk']}. "
            f"{top_result['reason']}"
        )
    else:
        briefing_text = "No flagged vendors right now. Everything looks routine."
    with st.spinner("Generating briefing..."):
        path = generate_briefing(briefing_text)
    st.audio(path)

# ---------- Beat 5: eval score ----------
st.subheader("Evaluation")
st.caption("Placeholder until eval.py exists and produces real numbers")
col1, col2, col3 = st.columns(3)
col1.metric("Precision", "—")
col2.metric("Recall", "—")
col3.metric("F1", "—")
