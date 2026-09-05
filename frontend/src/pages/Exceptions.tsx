import { useEffect, useState } from "react";
import { useBatch } from "../hooks/useBatch";
import { api } from "../services/api";
import { Panel, StatusBadge, Button, EmptyState } from "../components/ui";
import type { ExceptionRecord } from "../types/api";

export default function Exceptions() {
  const { batch, reconciled } = useBatch();
  const [items, setItems] = useState<ExceptionRecord[]>([]);
  const [selected, setSelected] = useState<ExceptionRecord | null>(null);
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!batch) return;
    const filters: Record<string, string> = {};
    if (typeFilter !== "ALL") filters.exception_type = typeFilter;
    if (statusFilter !== "ALL") filters.status = statusFilter;
    const results = await api.listExceptions(batch.id, filters);
    setItems(results);
    if (selected) {
      const updated = results.find((r) => r.id === selected.id);
      if (updated) setSelected(updated);
    }
  }

  useEffect(() => {
    if (batch && reconciled) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch, reconciled, typeFilter, statusFilter]);

  async function investigate(id: string) {
    setBusy(true);
    try {
      const updated = await api.investigateException(id);
      setSelected(updated);
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function resolve(id: string, action: string) {
    setBusy(true);
    try {
      const updated = await api.resolveException(id, action, "operator");
      setSelected(updated);
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Resolution failed");
    } finally {
      setBusy(false);
    }
  }

  if (!batch) {
    return <EmptyState title="No dataset loaded" description="Load the demo dataset from the top bar to begin." />;
  }
  if (!reconciled) {
    return <EmptyState title="Reconciliation not run yet" description="Run reconciliation from the Overview page to generate exceptions." />;
  }

  const exceptionTypes = Array.from(new Set(items.map((i) => i.exception_type)));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 h-full">
      <div className="lg:col-span-2">
        <Panel
          title={`Exceptions (${items.length})`}
          right={
            <div className="flex gap-2">
              <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="bg-ink-700 border border-ink-600 rounded-sm text-xs px-2 py-1">
                <option value="ALL">All types</option>
                {exceptionTypes.map((t) => (
                  <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                ))}
              </select>
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="bg-ink-700 border border-ink-600 rounded-sm text-xs px-2 py-1">
                <option value="ALL">All statuses</option>
                <option value="OPEN">Open</option>
                <option value="UNDER_REVIEW">Under review</option>
                <option value="RESOLVED">Resolved</option>
                <option value="UNRESOLVED">Unresolved</option>
                <option value="REJECTED">Rejected</option>
              </select>
            </div>
          }
        >
          <div className="space-y-1 max-h-[70vh] overflow-y-auto">
            {items.map((exc) => (
              <button
                key={exc.id}
                onClick={() => setSelected(exc)}
                className={`w-full text-left px-3 py-2 rounded-sm border ${
                  selected?.id === exc.id ? "border-brand bg-ink-700" : "border-transparent hover:bg-ink-700/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-mist-100">{exc.exception_type.replace(/_/g, " ")}</span>
                  <StatusBadge value={exc.severity} />
                </div>
                <div className="text-xs text-mist-500 mt-0.5 truncate">{exc.description}</div>
                <div className="flex items-center justify-between mt-1">
                  <span className="num text-xs text-mist-300">₹{exc.amount_affected.toLocaleString("en-IN")}</span>
                  <StatusBadge value={exc.status} />
                </div>
              </button>
            ))}
            {items.length === 0 && <div className="text-mist-500 text-sm p-4">No exceptions match these filters.</div>}
          </div>
        </Panel>
      </div>

      <div className="lg:col-span-3">
        {!selected ? (
          <EmptyState title="Select an exception" description="Choose an exception from the list to see full investigation detail." />
        ) : (
          <Panel title={selected.exception_type.replace(/_/g, " ")}>
            <div className="space-y-5">
              <section>
                <h3 className="text-xs uppercase text-mist-500 mb-1">What happened</h3>
                <p className="text-sm text-mist-100">{selected.description}</p>
              </section>

              <section className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <h3 className="text-xs uppercase text-mist-500 mb-1">Financial impact</h3>
                  <p className="num text-mist-100">₹{selected.amount_affected.toLocaleString("en-IN")}</p>
                </div>
                <div>
                  <h3 className="text-xs uppercase text-mist-500 mb-1">Severity</h3>
                  <StatusBadge value={selected.severity} />
                </div>
              </section>

              <section>
                <h3 className="text-xs uppercase text-mist-500 mb-1">AI Investigation</h3>
                {selected.ai_status === "NOT_ANALYZED" && (
                  <Button onClick={() => investigate(selected.id)} disabled={busy}>
                    {busy ? "Investigating…" : "Run AI Investigation"}
                  </Button>
                )}
                {selected.ai_status === "UNAVAILABLE" && (
                  <p className="text-sm text-mist-500 italic">
                    AI analysis unavailable — deterministic exception details above are still complete and usable.
                  </p>
                )}
                {selected.ai_status === "FAILED" && (
                  <p className="text-sm text-bad">AI analysis failed validation and was discarded; exception marked unresolved.</p>
                )}
                {selected.ai_status === "ANALYZED" && selected.ai_analysis && (
                  <div className="space-y-2 text-sm">
                    <div><span className="text-mist-500">Root cause: </span>{selected.ai_root_cause}</div>
                    <div><span className="text-mist-500">Confidence: </span><span className="num">{((selected.ai_confidence ?? 0) * 100).toFixed(0)}%</span></div>
                    <div><span className="text-mist-500">Recommended action: </span>{selected.recommended_action}</div>
                    <div className="text-mist-300">{String((selected.ai_analysis as Record<string, unknown>).explanation ?? "")}</div>
                  </div>
                )}
              </section>

              <section>
                <h3 className="text-xs uppercase text-mist-500 mb-1">Approval status</h3>
                <div className="flex items-center gap-2">
                  <StatusBadge value={selected.status} />
                  {selected.requires_human_approval && <span className="text-xs text-gold">Requires human approval</span>}
                </div>
              </section>

              {!["RESOLVED", "REJECTED"].includes(selected.status) && (
                <section className="flex gap-2 pt-2 border-t border-ink-600">
                  <Button onClick={() => resolve(selected.id, "APPROVE")} disabled={busy}>Approve</Button>
                  <Button variant="danger" onClick={() => resolve(selected.id, "REJECT")} disabled={busy}>Reject</Button>
                  <Button variant="secondary" onClick={() => resolve(selected.id, "REQUEST_INVESTIGATION")} disabled={busy}>Request Investigation</Button>
                  <Button variant="ghost" onClick={() => resolve(selected.id, "MARK_UNRESOLVED")} disabled={busy}>Mark Unresolved</Button>
                </section>
              )}
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}
