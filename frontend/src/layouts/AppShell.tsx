import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { useBatch } from "../hooks/useBatch";
import { api } from "../services/api";
import { Button } from "../components/ui";

const NAV_ITEMS = [
  { to: "/", label: "Overview", end: true },
  { to: "/reconciliation", label: "Reconciliation" },
  { to: "/exceptions", label: "Exceptions" },
  { to: "/qa", label: "Finance Q&A" },
  { to: "/forecast", label: "Cash Forecast" },
  { to: "/audit", label: "Audit Trail" },
  { to: "/evaluation", label: "Evaluation" },
];

export default function AppShell() {
  const { batch, setBatch, setReconciled } = useBatch();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listBatches().then((batches) => {
      if (batches.length > 0 && !batch) {
        setBatch(batches[0]);
      }
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadDemo() {
    setLoading(true);
    setError(null);
    try {
      const b = await api.loadDemoBatch(150, 42);
      setBatch(b);
      setReconciled(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load demo data");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen bg-ink-900 text-mist-100">
      <aside className="w-56 shrink-0 border-r border-ink-600 flex flex-col">
        <div className="px-4 py-4 border-b border-ink-600">
          <div className="font-semibold tracking-tight text-mist-100">FinRecon AI</div>
          <div className="text-xs text-mist-500 mt-0.5">Finance Controller</div>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-sm text-sm ${
                  isActive ? "bg-ink-700 text-mist-100 font-medium" : "text-mist-500 hover:text-mist-100 hover:bg-ink-800"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-ink-600 text-xs text-mist-500">
          Track 04 · AI Finance Controller
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b border-ink-600 flex items-center justify-between px-5 shrink-0">
          <div className="text-sm text-mist-300">
            {batch ? (
              <>
                <span className="text-mist-500">Batch:</span>{" "}
                <span className="num text-mist-100">{batch.label}</span>
              </>
            ) : (
              <span className="text-mist-500">No dataset loaded</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {error && <span className="text-xs text-bad">{error}</span>}
            <Button variant="secondary" onClick={loadDemo} disabled={loading}>
              {loading ? "Loading…" : "Load Demo Dataset"}
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
