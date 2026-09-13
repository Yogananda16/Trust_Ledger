"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Source = { url: string; title?: string; content: string };

type Signal = { label: string; pattern: string | null; hidden?: boolean };

type Vendor = {
  name: string;
  detail: string;
  signals: Signal[];
  evidence: string[];
  web_evidence: Source[];
  scenario: boolean;
  pin: number | null;
  amount: number | null;
  risk: "Low" | "Medium" | "High";
  reason: string | null;
  patterns: string[];
  sources: Source[];
};

type VendorData = {
  total_transactions: number;
  flagged_count: number;
  amount_at_risk: number;
  demo_count: number;
  vendors: Vendor[];
};

type Citation = { source: string; url: string };

type Play = {
  id: string;
  title: string;
  how: string;
  case: ({ headline: string; detail: string } & Citation) | null;
  fact: { text: string } & Citation;
  matches: string[];
};

const RISK_STYLES: Record<string, string> = {
  Low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Medium: "bg-amber-50 text-amber-700 border-amber-200",
  High: "bg-red-50 text-red-700 border-red-200",
};

// Set NEXT_PUBLIC_API_URL in Vercel to the hosted backend; local dev falls back to uvicorn.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const RISK_ORDER: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
const FILTERS = ["All", "High", "Medium", "Low"] as const;

const VIEWS = [
  { id: "vendors", label: "Vendors", short: "V" },
  { id: "playbook", label: "Fraud playbook", short: "P" },
] as const;

type View = (typeof VIEWS)[number]["id"];

function hostnameOf(url: string) {
  try {
    return new URL(url).hostname.replace("www.", "");
  } catch {
    return url;
  }
}

function SourceLink({ source, url }: Citation) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-600 hover:underline"
    >
      {source}
    </a>
  );
}

export default function Home() {
  const [data, setData] = useState<VendorData | null>(null);
  const [playbook, setPlaybook] = useState<Play[]>([]);
  const [view, setView] = useState<View>("vendors");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [playingVendor, setPlayingVendor] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [patternFilter, setPatternFilter] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/vendors`)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => {
        setLoadFailed(true);
        setLoading(false);
      });
    fetch(`${API_URL}/api/playbook`)
      .then((r) => r.json())
      .then(setPlaybook)
      .catch(() => {});
  }, []);

  const playById = useMemo(
    () => Object.fromEntries(playbook.map((p) => [p.id, p])) as Record<string, Play>,
    [playbook]
  );

  const visibleVendors = useMemo(() => {
    if (!data) return [];
    return data.vendors
      .filter((v) => filter === "All" || v.risk === filter)
      .filter((v) => !patternFilter || v.signals.some((s) => s.pattern === patternFilter))
      .filter((v) => v.name.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => {
        // Pinned vendors lead the list in their pinned order.
        if (a.pin !== b.pin) return (a.pin ?? Infinity) - (b.pin ?? Infinity);
        const byRisk = RISK_ORDER[a.risk] - RISK_ORDER[b.risk];
        if (byRisk !== 0) return byRisk;
        return (b.amount ?? 0) - (a.amount ?? 0);
      });
  }, [data, filter, patternFilter, search]);

  const counts = useMemo(() => {
    const c = { High: 0, Medium: 0, Low: 0 };
    data?.vendors.forEach((v) => c[v.risk]++);
    return c;
  }, [data]);

  const showMatches = (patternId: string) => {
    setPatternFilter(patternId);
    setFilter("All");
    setSearch("");
    setView("vendors");
  };

  const playBriefing = async (name: string) => {
    if (playingVendor === name && audioRef.current) {
      audioRef.current.pause();
      setPlayingVendor(null);
      return;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlayingVendor(name);
    try {
      const res = await fetch(
        `${API_URL}/api/briefing/${encodeURIComponent(name)}`
      );
      const blob = await res.blob();
      const audio = new Audio(URL.createObjectURL(blob));
      audioRef.current = audio;
      audio.onended = () => {
        setPlayingVendor(null);
        audioRef.current = null;
      };
      await audio.play();
    } catch {
      setPlayingVendor(null);
      audioRef.current = null;
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 text-neutral-900 flex">
      <aside
        className={`${sidebarOpen ? "w-56" : "w-16"
          } shrink-0 border-r border-neutral-200 bg-white transition-all duration-200`}
      >
        <div className="p-4 flex items-center justify-between">
          {sidebarOpen && (
            <span className="text-sm font-semibold tracking-tight">
              TrustLedger
            </span>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-md p-1.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700"
            title={sidebarOpen ? "Collapse" : "Expand"}
          >
            {sidebarOpen ? "«" : "»"}
          </button>
        </div>

        <nav className="px-2 mt-2 space-y-1">
          {VIEWS.map((item) => (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              title={item.label}
              className={`w-full text-left rounded-lg px-3 py-2 text-sm font-medium ${view === item.id
                ? "bg-neutral-100 text-neutral-900"
                : "text-neutral-500 hover:bg-neutral-50 hover:text-neutral-900"
                }`}
            >
              {sidebarOpen ? item.label : item.short}
            </button>
          ))}
        </nav>
      </aside>

      <main className="flex-1 overflow-auto">
        {view === "vendors" && (
          <div className="max-w-5xl px-10 py-12">
            <div className="mb-10">
              <h1 className="text-2xl font-semibold tracking-tight">Vendors</h1>
              <p className="text-sm text-neutral-500 mt-1">
                Risk monitoring across your Rho transactions
              </p>
            </div>

            {loading && (
              <p className="text-sm text-neutral-500">
                Analyzing vendors… If the server was asleep, this can take up to a minute.
              </p>
            )}

            {loadFailed && (
              <p className="text-sm text-red-600">
                Couldn&apos;t reach the analysis server. Refresh the page in a minute.
              </p>
            )}

            {data && (
              <>
                <div className="grid grid-cols-3 gap-4 mb-10">
                  {[
                    ["Transactions", data.total_transactions],
                    ["Flagged", data.flagged_count],
                    ["At risk", `$${data.amount_at_risk?.toLocaleString() ?? 0}`],
                  ].map(([label, value]) => (
                    <div
                      key={label as string}
                      className="rounded-xl border border-neutral-200 bg-white p-5"
                    >
                      <p className="text-xs text-neutral-500 mb-1">{label}</p>
                      <p className="text-2xl font-semibold">{value}</p>
                    </div>
                  ))}
                </div>

                <div className="flex items-center gap-3 mb-5">
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search vendors…"
                    className="flex-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm outline-none focus:border-neutral-400"
                  />
                  <div className="flex gap-1">
                    {FILTERS.map((f) => (
                      <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`rounded-lg px-3 py-2 text-xs font-medium border ${filter === f
                          ? "bg-neutral-900 text-white border-neutral-900"
                          : "bg-white border-neutral-200 text-neutral-600 hover:bg-neutral-50"
                          }`}
                      >
                        {f}
                        {f !== "All" && (
                          <span className="ml-1.5 opacity-60">{counts[f]}</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {patternFilter && (
                  <div className="mb-3 flex items-center gap-2 text-xs text-neutral-600">
                    Showing vendors matching
                    <span className="font-medium text-neutral-900">
                      {playById[patternFilter]?.title}
                    </span>
                    <button
                      onClick={() => setPatternFilter(null)}
                      className="rounded-md border border-neutral-200 bg-white px-2 py-0.5 text-neutral-500 hover:text-neutral-900"
                    >
                      Clear
                    </button>
                  </div>
                )}

                <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
                  {visibleVendors.length === 0 && (
                    <p className="px-5 py-8 text-sm text-neutral-500 text-center">
                      No vendors match.
                    </p>
                  )}
                  {visibleVendors.map((v, i) => {
                    const pattern = v.signals.find((s) => s.pattern)?.pattern;
                    const patternTitle = pattern ? playById[pattern]?.title : undefined;
                    return (
                      <div
                        key={v.name}
                        className={i > 0 ? "border-t border-neutral-100" : ""}
                      >
                        <div className="w-full flex items-center gap-4 px-5 py-4 hover:bg-neutral-50">
                          <span className="text-xs text-neutral-400 w-6 shrink-0">
                            {i + 1}
                          </span>
                          <button
                            onClick={() =>
                              setExpanded(expanded === v.name ? null : v.name)
                            }
                            disabled={!v.reason}
                            className="text-left flex-1"
                          >
                            <p className="text-sm font-medium">{v.name}</p>
                            <p className="text-xs text-neutral-500 mt-0.5">
                              {[v.detail, v.amount ? `$${v.amount.toFixed(2)}` : ""]
                                .filter(Boolean)
                                .join(" · ")}
                            </p>
                            {v.signals?.some((s) => !s.hidden) && (
                              <div className="flex flex-wrap gap-1.5 mt-2">
                                {v.signals.filter((s) => !s.hidden).map((s) => (
                                  <span
                                    key={s.label}
                                    className={`rounded-md px-2 py-0.5 text-[11px] ${s.pattern
                                      ? "border border-neutral-300 bg-white text-neutral-900"
                                      : "bg-neutral-100 text-neutral-700"
                                      }`}
                                  >
                                    {s.label}
                                  </span>
                                ))}
                              </div>
                            )}
                          </button>

                          <div className="flex items-center gap-2">
                            {v.risk !== "Low" && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  playBriefing(v.name);
                                }}
                                className="rounded-md border border-neutral-200 px-2.5 py-1 text-xs hover:bg-neutral-100"
                                title="Hear why this was flagged"
                              >
                                {playingVendor === v.name ? "❚❚" : "▶"}
                              </button>
                            )}
                            <span
                              className={`rounded-md border px-2.5 py-1 text-xs font-medium ${RISK_STYLES[v.risk]}`}
                            >
                              {v.risk}
                            </span>
                          </div>
                        </div>

                        {expanded === v.name && v.reason && (
                          <div className="bg-neutral-50 px-5 py-4 text-sm">
                            <p className="text-xs font-medium text-neutral-500 mb-2">
                              Why this was flagged
                            </p>
                            <p className="text-neutral-700 mb-3">{v.reason}</p>
                            {v.evidence?.length > 0 && (
                              <div className="mb-4 rounded-lg border border-neutral-200 bg-white p-4">
                                <p className="text-xs font-medium text-neutral-500 mb-2">
                                  In your records
                                </p>
                                <ul className="space-y-1.5">
                                  {v.evidence.map((e) => (
                                    <li key={e} className="flex gap-2 text-neutral-700">
                                      <span className="text-neutral-400">•</span>
                                      <span>{e}</span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {v.web_evidence?.length > 0 && (
                              <div className="mb-4">
                                <p className="text-xs font-medium text-neutral-500 mb-2">
                                  On the web{patternTitle && `: ${patternTitle}`}
                                </p>
                                <ul className="space-y-1.5">
                                  {v.web_evidence.slice(0, 3).map((s) => (
                                    <li key={s.url} className="text-xs">
                                      <a
                                        href={s.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-600 hover:underline"
                                      >
                                        {s.title ?? hostnameOf(s.url)}
                                      </a>
                                      <span className="ml-2 text-neutral-400">
                                        {hostnameOf(s.url)}
                                      </span>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {v.patterns.length > 0 && (
                              <>
                                <p className="text-xs font-medium text-neutral-500 mb-2">
                                  Matched fraud patterns
                                </p>
                                <ul className="space-y-1">
                                  {v.patterns.slice(0, 2).map((p, j) => (
                                    <li key={j} className="text-neutral-600 text-xs">
                                      {p}
                                    </li>
                                  ))}
                                </ul>
                              </>
                            )}
                            {v.sources?.length > 0 && (
                              <div className="mt-4">
                                <p className="text-xs font-medium text-neutral-500 mb-2">
                                  Sources checked
                                </p>
                                <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
                                  {v.sources.slice(0, 3).map((s, j) => (
                                    <li key={j}>
                                      <a
                                        href={s.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-xs text-blue-600 hover:underline break-all"
                                      >
                                        {hostnameOf(s.url)}
                                      </a>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}

        {view === "playbook" && (
          <div className="max-w-5xl px-10 py-12">
            <div className="mb-10">
              <h1 className="text-2xl font-semibold tracking-tight">Fraud playbook</h1>
              <p className="text-sm text-neutral-500 mt-1">
                How payment fraud gets past vendor onboarding checks, and where it
                shows up in your data
              </p>
            </div>

            {playbook.length === 0 && (
              <p className="text-sm text-neutral-500">Loading playbook…</p>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              {playbook.map((p) => (
                <div
                  key={p.id}
                  className="flex flex-col rounded-xl border border-neutral-200 bg-white p-5"
                >
                  <h2 className="text-base font-semibold">{p.title}</h2>
                  <p className="text-sm text-neutral-600 mt-2">{p.how}</p>

                  {p.case && (
                    <div className="mt-4 rounded-lg bg-neutral-50 px-4 py-3">
                      <p className="text-sm font-medium">{p.case.headline}</p>
                      <p className="text-xs text-neutral-600 mt-1">
                        {p.case.detail} <SourceLink {...p.case} />
                      </p>
                    </div>
                  )}

                  <p className="text-xs text-neutral-500 mt-4">
                    {p.fact.text} <SourceLink {...p.fact} />
                  </p>

                  <div className="mt-auto pt-5">
                    <button
                      onClick={() => showMatches(p.id)}
                      disabled={p.matches.length === 0}
                      className="rounded-lg border border-neutral-200 px-3 py-1.5 text-xs font-medium hover:bg-neutral-50 disabled:cursor-default disabled:text-neutral-400 disabled:hover:bg-white"
                    >
                      {p.matches.length > 0
                        ? `Found in your data: ${p.matches.length} →`
                        : "Not found in your data"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
