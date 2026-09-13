# TrustLedger

An AI agent that flags risky vendor payments before they clear — built on Rho's transaction API for the LOCK IN Hack (Rho, Sep 12-13 2026).

## The problem

Startups pay vendors with almost no automated check on who they're actually paying. Business email compromise and vendor impersonation cost businesses billions annually (FBI IC3: $3.05B reported in 2025 alone), and small companies have far less internal fraud detection infrastructure than large enterprises. Existing vendor-fraud tools (e.g. Trustpair) are built for large enterprises with dedicated procurement systems — nothing serves a lean startup that just has a bank account.

## The solution

TrustLedger reads a company's Rho transactions, flags new or unusual vendors, checks them against known fraud patterns (RAG) and live web results (Tavily), and returns a risk verdict with evidence — spoken aloud via ElevenLabs.

## Architecture

1. **Ingestion** (`pull_data.py`) — pulls accounts/transactions from Rho's sandbox API
2. **Novelty detection** (`pipeline/novelty.py`) — flags vendors never paid before, or paid unusually large amounts
3. **RAG** (`pipeline/rag.py` + `data/fraud_patterns.json`) — retrieves matching fraud patterns from an 18-document knowledge base (sourced from FTC/FBI research) via a local Chroma vector store
4. **Live verification** (`pipeline/tavily_check.py`) — real-time web search for domain age, complaints, and business legitimacy
5. **Verdict synthesis** (`pipeline/verdict.py`) — an LLM combines RAG + Tavily evidence into a Low/Medium/High risk tier with a stated reason
6. **Voice output** (`pipeline/voice.py`) — speaks the top risk alert aloud
7. **Dashboard** (`app.py`) — Streamlit UI tying it together

## Tech stack

Rho sandbox API · Groq (LLM) · Chroma (vector store) · Tavily (web search) · ElevenLabs (voice) · Streamlit

## Setup

1. Clone the repo and create a virtual environment
2. `pip install -r requirements.txt`
3. Create a `.env` file with:
