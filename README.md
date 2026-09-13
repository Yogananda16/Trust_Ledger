# TrustLedger

Flags risky vendor payments and shows the evidence behind every flag. Built on Rho's transaction API for the LOCK IN Hack (Rho, Sep 12-13 2026).

**Live app:** https://trust-ledger-ai.vercel.app

## The problem

Companies vet a vendor once, when it's added. Most payment fraud gets past that: changed bank details, reused invoices, look-alike vendors, pressured wires and insiders. Business email compromise alone cost US businesses $3.05B in 2025 (FBI IC3). Enterprise tools exist; a startup with just a bank account has nothing.

## How it works

1. **Detect:** rules flag new vendors, bank-detail changes, duplicate or look-alike invoices, payment bursts, just-under-limit payments and more.
2. **Explain:** facts from the company's own records ("In your records").
3. **Verify:** Tavily searches the exact vendor (company profile or scam and enforcement records) and public reporting on the fraud pattern.
4. **Rate:** an LLM combines the evidence and matched fraud patterns (RAG) into a Low, Medium or High verdict with a reason.
5. **Alert:** a spoken briefing via ElevenLabs.

## Tech stack

Next.js · FastAPI · Groq · Tavily · Chroma · ElevenLabs · Rho sandbox API. Frontend on Vercel, backend on Hugging Face Spaces.

## Run locally

Create a `.env` with `GROQ_API_KEY`, `TAVILY_API_KEY` and `ELEVENLABS_API_KEY`, then:

```bash
pip install -r requirements.txt
uvicorn api:app --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

Full details (architecture, rules, data, deployment): [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)
