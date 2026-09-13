"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Vendor = {
  name: string;
  detail: string;
  amount: number | null;
  risk: "Low" | "Medium" | "High";
  reason: string | null;
  patterns: string[];
};

type VendorData = {
  total_transactions: number;
  flagged_count: number;
  amount_at_risk: number;
  vendors: Vendor[];
};

const RISK_STYLES: Record<string, string> = {
  Low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Medium: "bg-amber-50 text-amber-700 border-amber-200",
  High: "bg-red-50 text-red-700 border-red-200",
};

const RISK_ORDER: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
const FILTERS = ["All", "High", "Medium", "Low"] as const;

export default function Home() {
  const [data, setData] = useState<VendorData | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [playingVendor, setPlayingVendor] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/api/vendors")
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const visibleVendors = useMemo(() => {
    if (!data) return [];
    return data.vendors
      .filter((v) => filter === "All" || v.risk === filter)
      .filter((v) => v.name.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => {
        const byRisk = RISK_ORDER[a.risk] - RISK_ORDER[b.risk];
        if (byRisk !== 0) return byRisk;
        return (b.amount ?? 0) - (a.amount ?? 0);
      });
  }, [data, filter, search]);

  const counts = useMemo(() => {
    const c = { High: 0, Medium: 0, Low: 0 };
    data?.vendors.forEach((v) => c[v.risk]++);
    return c;
  }, [data]);

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
        `http://localhost:8000/api/briefing/${encodeURIComponent(name)}`
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

        <nav className="px-2 mt-2">
          <div className="rounded-lg bg-neutral-100 px-3 py-2 text-sm font-medium">
            {sidebarOpen ? "Vendors" : "V"}
          </div>
        </nav>

        {sidebarOpen && data && (
          <div className="px-5 mt-8 space-y-4">
            <div>
              <p className="text-xs text-neutral-500">High risk</p>
              <p className="text-lg font-semibold text-red-600">{counts.High}</p>
            </div>
            <div>
              <p className="text-xs text-neutral-500">Medium risk</p>
              <p className="text-lg font-semibold text-amber-600">
                {counts.Medium}
              </p>
            </div>
            <div>
              <p className="text-xs text-neutral-500">Cleared</p>
              <p className="text-lg font-semibold text-emerald-600">
                {counts.Low}
              </p>
            </div>
          </div>
        )}
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="max-w-5xl px-10 py-12">
          <div className="mb-10">
            <h1 className="text-2xl font-semibold tracking-tight">Vendors</h1>
            <p className="text-sm text-neutral-500 mt-1">
              Risk monitoring across your Rho transactions
            </p>
          </div>

          {loading && (
            <p className="text-sm text-neutral-500">Analyzing vendors…</p>
          )}

          {data && (
            <>
              <div className="grid grid-cols-4 gap-4 mb-10">
                {[
                  ["Transactions", data.total_transactions],
                  ["Flagged", data.flagged_count],
                  ["At risk", `$${data.amount_at_risk?.toLocaleString() ?? 0}`],
                  ["Detection F1", "91%"],
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

              <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
                {visibleVendors.length === 0 && (
                  <p className="px-5 py-8 text-sm text-neutral-500 text-center">
                    No vendors match.
                  </p>
                )}
                {visibleVendors.map((v, i) => (
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
                          {v.detail}
                          {v.amount ? ` · $${v.amount.toFixed(2)}` : ""}
                        </p>
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
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}