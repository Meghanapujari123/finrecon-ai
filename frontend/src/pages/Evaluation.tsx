import { useEffect, useState } from "react";
import { useBatch } from "../hooks/useBatch";
import { api } from "../services/api";
import { Panel, StatTile, EmptyState } from "../components/ui";
import type { EvaluationResult, ExceptionRecord } from "../types/api";

export default function Evaluation() {
  const { batch, reconciled } = useBatch();
  const [ev, setEv] = useState<EvaluationResult | null>(null);
  const [unresolved, setUnresolved] = useState<ExceptionRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!batch || !reconciled) return;
    api.runEvaluation(batch.id).then(setEv).catch((e) => setError(e.message));
    api.listExceptions(batch.id, { status: "UNRESOLVED" }).then(setUnresolved);
  }, [batch, reconciled]);

  if (!batch) {
    return <EmptyState title="No dataset loaded" description="Load the demo dataset from the top bar to begin." />;
  }
  if (!reconciled) {
    return <EmptyState title="Reconciliation not run yet" description="Run reconciliation from the Overview page to generate evaluation metrics." />;
  }
  if (error) {
    return <EmptyState title="Evaluation unavailable" description={error} />;
  }
  if (!ev) {
    return <div className="text-mist-500 text-sm">Computing evaluation metrics…</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-mist-100">Evaluation</h1>
      <p className="text-sm text-mist-500 max-w-2xl">
        Every metric below is computed from this run against the dataset's known ground-truth labels — nothing here
        is hardcoded.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile label="Dataset Size" value={String(ev.dataset_size)} />
        <StatTile label="Match Accuracy" value={`${(ev.match_accuracy * 100).toFixed(1)}%`} tone="good" />
        <StatTile label="Precision" value={`${(ev.precision * 100).toFixed(1)}%`} />
        <StatTile label="Recall" value={`${(ev.recall * 100).toFixed(1)}%`} />
        <StatTile label="F1 Score" value={`${(ev.f1 * 100).toFixed(1)}%`} tone="good" />
        <StatTile label="False Positives" value={String(ev.false_positive_count)} tone="bad" />
        <StatTile label="False Negatives" value={String(ev.false_negative_count)} tone="bad" />
        <StatTile label="False Matches" value={String(ev.false_match_count)} tone="bad" />
        <StatTile label="Exception Classification Accuracy" value={`${(ev.exception_classification_accuracy * 100).toFixed(1)}%`} />
        <StatTile label="Processing Time" value={`${ev.evaluation_processing_time_ms} ms`} />
        <StatTile label="Amount Correctly Reconciled" value={`₹${ev.amount_correctly_reconciled.toLocaleString("en-IN")}`} tone="good" />
        <StatTile label="Amount Unresolved" value={`₹${ev.amount_affected_total.toLocaleString("en-IN")}`} tone="bad" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatTile label="Resolved Automatically" value={String(ev.resolved_exception_count)} tone="good" />
        <StatTile label="Requires Human Review" value={String(ev.open_exception_count)} tone="gold" />
        <StatTile label="Unresolved" value={String(ev.unresolved_exception_count)} tone="bad" />
      </div>

      <Panel title="Exceptions we could not confidently resolve">
        {unresolved.length === 0 ? (
          <p className="text-sm text-mist-500">None in this run — every exception is either resolved or awaiting review.</p>
        ) : (
          <ul className="space-y-2">
            {unresolved.map((u) => (
              <li key={u.id} className="text-sm text-mist-300 border-b border-ink-700/60 pb-2">
                <span className="text-bad font-medium">{u.exception_type.replace(/_/g, " ")}</span> — {u.description}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
