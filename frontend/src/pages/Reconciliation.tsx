import { useEffect, useState } from "react";
import { useBatch } from "../hooks/useBatch";
import { api } from "../services/api";
import { Panel, StatusBadge, EmptyState, Button } from "../components/ui";
import type { ReconciliationResultRow } from "../types/api";

export default function Reconciliation() {
  const { batch, reconciled, setReconciled } = useBatch();
  const [rows, setRows] = useState<ReconciliationResultRow[]>([]);
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [running, setRunning] = useState(false);

  async function load() {
    if (!batch) return;
    const results = await api.getReconciliationResults(batch.id);
    setRows(results);
  }

  useEffect(() => {
    if (batch && reconciled) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch, reconciled]);

  async function runReconciliation() {
    if (!batch) return;
    setRunning(true);
    try {
      const result = await api.runReconciliation(batch.id);
      if (!result.error) {
        setReconciled(true);
        await load();
      }
    } finally {
      setRunning(false);
    }
  }

  if (!batch) {
    return <EmptyState title="No dataset loaded" description="Load the demo dataset from the top bar to begin." />;
  }

  const filtered = rows.filter((r) => {
    if (statusFilter !== "ALL" && r.match_status !== statusFilter) return false;
    if (filter && !JSON.stringify(r).toLowerCase().includes(filter.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-mist-100">Reconciliation</h1>
        <Button onClick={runReconciliation} disabled={running}>
          {running ? "Running…" : reconciled ? "Re-run Reconciliation" : "Run Full Reconciliation"}
        </Button>
      </div>

      {!reconciled ? (
        <EmptyState title="Not yet run" description="Run reconciliation to see matched records and exceptions here." />
      ) : (
        <Panel
          title={`Results (${filtered.length} of ${rows.length})`}
          right={
            <div className="flex gap-2">
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-ink-700 border border-ink-600 rounded-sm text-xs px-2 py-1 text-mist-100"
              >
                <option value="ALL">All statuses</option>
                <option value="MATCHED">Matched</option>
                <option value="EXCEPTION">Exception</option>
              </select>
              <input
                placeholder="Search…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-ink-700 border border-ink-600 rounded-sm text-xs px-2 py-1 text-mist-100 placeholder:text-mist-500"
              />
            </div>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-mist-500 text-xs uppercase border-b border-ink-600">
                  <th className="py-2 pr-4">Payment</th>
                  <th className="py-2 pr-4">Bank Ref</th>
                  <th className="py-2 pr-4">Ledger</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Match Method</th>
                  <th className="py-2 pr-4 text-right">Confidence</th>
                  <th className="py-2 pr-4 text-right">Amount Diff</th>
                  <th className="py-2 pr-4">Reason</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} className="border-b border-ink-700/60 hover:bg-ink-700/40">
                    <td className="py-2 pr-4 num text-xs text-mist-300">{r.payment_id ? r.payment_id.slice(0, 8) : "—"}</td>
                    <td className="py-2 pr-4 num text-xs text-mist-300">{r.bank_transaction_id ? r.bank_transaction_id.slice(0, 8) : "—"}</td>
                    <td className="py-2 pr-4 num text-xs text-mist-300">{r.ledger_entry_id ? r.ledger_entry_id.slice(0, 8) : "—"}</td>
                    <td className="py-2 pr-4"><StatusBadge value={r.match_status} /></td>
                    <td className="py-2 pr-4 text-xs text-mist-300">{r.match_method.replace(/_/g, " ")}</td>
                    <td className="py-2 pr-4 num text-right">{(r.confidence * 100).toFixed(0)}%</td>
                    <td className="py-2 pr-4 num text-right">{r.amount_difference !== 0 ? r.amount_difference.toFixed(2) : "—"}</td>
                    <td className="py-2 pr-4 text-xs text-mist-500 max-w-xs truncate">{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
