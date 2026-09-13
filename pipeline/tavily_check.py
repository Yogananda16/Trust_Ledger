import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(override=True)
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

MAX_LINKS = 3

# Pattern searches don't depend on the vendor, so each runs once and is reused.
PATTERN_CACHE = Path("data/web_evidence_cache.json")

# Authorities and major news outlets, so pattern evidence isn't vendor marketing.
TRUSTED_DOMAINS = [
    "fbi.gov", "ic3.gov", "ftc.gov", "cisa.gov", "justice.gov", "sec.gov", "irs.gov",
    "nacha.org", "acfe.com", "financialprofessionals.org", "bbb.org", "aba.com",
    "reuters.com", "bloomberg.com", "cnbc.com", "cnn.com", "bbc.com", "wsj.com",
    "forbes.com", "bleepingcomputer.com", "krebsonsecurity.com",
]


def _links(results):
    return [
        {"url": r["url"], "title": r.get("title") or r["url"], "content": r["content"][:300]}
        for r in results[:MAX_LINKS]
    ]


def _is_trusted(url):
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in TRUSTED_DOMAINS)


LEGAL_SUFFIXES = {"inc", "llc", "llp", "ltd", "co", "corp", "corporation", "company", "sac", "plc", "gmbh"}


def _plain(text):
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _core_name(vendor_name):
    words = _plain(vendor_name).split()
    while len(words) > 1 and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def check_vendor(vendor_name: str) -> list:
    core = _core_name(vendor_name)
    try:
        # A verification search: does this business really exist, and where?
        response = client.search(
            query=f'"{core}" company headquarters founded official website',
            search_depth="advanced",
            max_results=8,
        )
    except Exception as e:
        print("Tavily error:", e)
        return []
    # Keep only pages naming this exact vendor, so similarly named companies can't count as evidence.
    about_vendor = [
        r for r in response["results"]
        if re.search(rf"\b{re.escape(core)}\b", _plain(f"{r.get('title', '')} {r['content']}"))
    ]
    return _links(about_vendor)


def _source_rank(url):
    # Government records first, then trusted outlets, then everything else.
    host = urlparse(url).hostname or ""
    if host.endswith(".gov"):
        return 0
    return 1 if _is_trusted(url) else 2


def check_vendor_reputation(vendor_name: str) -> list:
    """Search for scam reports, warnings or enforcement actions naming this exact vendor."""
    core = _core_name(vendor_name)
    try:
        response = client.search(
            query=f'"{core}" scam fraud FTC lawsuit complaint warning',
            search_depth="advanced",
            max_results=10,
        )
    except Exception as e:
        print("Tavily error:", e)
        return []
    seen, kept = set(), []
    for r in response["results"]:
        names_vendor = re.search(rf"\b{re.escape(core)}\b", _plain(f"{r.get('title', '')} {r['content']}"))
        if names_vendor and _normalize(r["url"]) not in seen:
            seen.add(_normalize(r["url"]))
            kept.append(r)
    return _links(sorted(kept, key=lambda r: _source_rank(r["url"])))


def _normalize(url):
    parsed = urlparse(url)
    return (parsed.hostname or "").removeprefix("www.") + parsed.path.rstrip("/").removesuffix("/amp")


def search_pattern(pattern_id: str, query: str, keywords: list = None) -> list:
    cache = json.loads(PATTERN_CACHE.read_text()) if PATTERN_CACHE.exists() else {}
    if pattern_id not in cache:
        try:
            response = client.search(
                query=query,
                search_depth="advanced",
                max_results=10,
                include_domains=TRUSTED_DOMAINS,
            )
        except Exception as e:
            print("Tavily error:", e)
            return []
        # Tavily sometimes pads results with other sites or off-topic pages, so filter again here.
        seen, kept = set(), []
        for r in response["results"]:
            text = f"{r.get('title', '')} {r['content']}".lower()
            on_topic = not keywords or any(k in text for k in keywords)
            keys = {_normalize(r["url"]), (r.get("title") or "").strip().lower()}
            if _is_trusted(r["url"]) and on_topic and not keys & seen:
                seen |= keys
                kept.append(r)
        cache[pattern_id] = _links(kept)
        PATTERN_CACHE.write_text(json.dumps(cache, indent=2))
    return cache[pattern_id]
