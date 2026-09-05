import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useBatch } from "../hooks/useBatch";
import { api } from "../services/api";
import { Panel, StatTile, Button, EmptyState } from "../components/ui";
import type { DashboardSummary, ExceptionRecord, ReconciliationRunResult } from "../types/api";

const CHART_COLORS = ["#5B8DEF", "#D6A756", "#E2685C", "#3FB88F", "#8B98A6", "#3F6BC4"];

export default function Overview() {
  const { batch, reconciled, setReconciled } = useBatch();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [exceptions, setExceptions] = useState<ExceptionRecord[]>([]);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<ReconciliationRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadSummary() {
    if (!batch) return;
    try {
      const [s, exc] = await Promise.all([api.getDashboard(batch.id), api.listExceptions(batch.id)]);
      setSummary(s);
      setExceptions(exc);
    } catch {
      setSummary(null);
    }
  }

  useEffect(() => {
    if (batch && reconciled) loadSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batch, reconciled]);

  async function runReconciliation() {
    if (!batch) return;
    setRunning(true);
    setError(null);
    try {
      const result = await api.runReconciliation(batch.id);
      setRunResult(result);
      if (!result.error) {
        setReconciled(true);
      } else {
        setError(result.error);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reconciliation failed");
    } finally {
      setRunning(false);
    }
  }

  if (!batch) {
    return (
      <EmptyState
        title="No dataset loaded"
        description="Load the demo dataset from the top bar, or upload your own payment, bank, and ledger CSVs, to get started."
      />
    );
  }

  if (!reconciled) {
    return (
      <EmptyState
        title="Dataset loaded — reconciliation not run yet"
        description={`${batch.label} is ready. Run reconciliation to match payments, bank settlements, and ledger entries, and surface exceptions.`}
        action={
          <div className="space-y-2">
            <Button onClick={runReconciliation} disabled={running}>
              {running ? "Running reconciliation…" : "Run Full Reconciliation"}
            </Button>
            {error && <div className="text-bad text-sm">{error}</div>}
            {runResult && !runResult.error && (
              <div className="text-mist-500 text-xs num">
                {runResult.total_records} records processed in {runResult.processing_time_ms}ms (
                {runResult.throughput_records_per_second} rec/s)
              </div>
            )}
          </div>
        }
      />
    );
  }

  const exceptionsByType = Object.entries(
    exceptions.reduce<Record<string, number>>((acc, e) => {
      acc[e.exception_type] = (acc[e.exception_type] || 0) + 1;
      return acc;
    }, {})
  ).map(([name, value]) => ({ name: name.replace(/_/g, " "), value }));

  const amountByType = Object.entries(
    exceptions.reduce<Record<string, number>>((acc, e) => {
      acc[e.exception_type] = (acc[e.exception_type] || 0) + e.amount_affected;
      return acc;
    }, {})
  ).map(([name, amount]) => ({ name: name.replace(/_/g, " "), amount: Math.round(amount) }));

  const statusBreakdown = [
    { name: "Matched", value: summary?.matched ?? 0 },
    { name: "Exception", value: summary?.exceptions ?? 0 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-mist-100">Overview</h1>
        <Button variant="secondary" onClick={runReconciliation} disabled={running}>
          {running ? "Re-running…" : "Re-run Reconciliation"}
        </Button>
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatTile label="Total Records" value={String(summary.total_records)} />
          <StatTile label="Matched" value={String(summary.matched)} tone="good" />
          <StatTile label="Exceptions" value={String(summary.exceptions)} tone="gold" />
          <StatTile label="Match Rate" value={`${(summary.match_rate * 100).toFixed(1)}%`} />
          <StatTile
            label="Accuracy (vs ground truth)"
            value={summary.accuracy != null ? `${(summary.accuracy * 100).toFixed(1)}%` : "—"}
            tone="good"
          />
          <StatTile
            label="Throughput"
            value={runResult ? `${runResult.throughput_records_per_second} rec/s` : "—"}
          />
          <StatTile label="Amount Affected" value={`₹${summary.amount_affected.toLocaleString("en-IN")}`} tone="bad" />
          <StatTile label="Needs Human Review" value={String(summary.human_review_required)} tone="gold" />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Reconciliation status">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={statusBreakdown} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                {statusBreakdown.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? "#3FB88F" : "#D6A756"} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#1B232C", border: "1px solid #2C3742", borderRadius: 4 }} />
            </PieChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Exception categories">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={exceptionsByType} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                {exceptionsByType.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#1B232C", border: "1px solid #2C3742", borderRadius: 4 }} />
            </PieChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Financial amount by exception type">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={amountByType} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid stroke="#222C36" horizontal={false} />
              <XAxis type="number" stroke="#8B98A6" fontSize={11} />
              <YAxis type="category" dataKey="name" stroke="#8B98A6" fontSize={11} width={140} />
              <Tooltip contentStyle={{ background: "#1B232C", border: "1px solid #2C3742", borderRadius: 4 }} />
              <Bar dataKey="amount" fill="#5B8DEF" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Processing performance">
          {runResult ? (
            <div className="space-y-3 num text-sm">
              <div className="flex justify-between"><span className="text-mist-500">Total records</span><span>{runResult.total_records}</span></div>
              <div className="flex justify-between"><span className="text-mist-500">Processing time</span><span>{runResult.processing_time_ms} ms</span></div>
              <div className="flex justify-between"><span className="text-mist-500">Throughput</span><span>{runResult.throughput_records_per_second} rec/s</span></div>
              <div className="flex justify-between"><span className="text-mist-500">Match rate</span><span>{(runResult.match_rate * 100).toFixed(1)}%</span></div>
            </div>
          ) : (
            <div className="text-mist-500 text-sm">Run reconciliation this session to see fresh timing data.</div>
          )}
        </Panel>
      </div>
    </div>
  );
}
