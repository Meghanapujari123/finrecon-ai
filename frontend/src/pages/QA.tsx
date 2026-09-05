import { useState } from "react";
import { useBatch } from "../hooks/useBatch";
import { api } from "../services/api";
import { Panel, Button, EmptyState } from "../components/ui";
import type { QAResponse } from "../types/api";

const SUGGESTED = [
  "How much money is currently at risk?",
  "What are the top three exception types?",
  "Which settlements are missing?",
  "How much was reconciled?",
  "How many transactions require human review?",
  "What is causing the largest financial discrepancy?",
];

export default function QA() {
  const { batch, reconciled } = useBatch();
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<{ question: string; response: QAResponse }[]>([]);
  const [loading, setLoading] = useState(false);

  async function ask(q: string) {
    if (!batch || !q.trim()) return;
    setLoading(true);
    try {
      const response = await api.askQuestion(batch.id, q);
      setHistory((h) => [{ question: q, response }, ...h]);
      setQuestion("");
    } finally {
      setLoading(false);
    }
  }

  if (!batch) {
    return <EmptyState title="No dataset loaded" description="Load the demo dataset from the top bar to begin." />;
  }
  if (!reconciled) {
    return <EmptyState title="Reconciliation not run yet" description="Run reconciliation from the Overview page first — Q&A answers come from that data." />;
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-lg font-semibold text-mist-100">Finance Q&A</h1>

      <Panel>
        <div className="flex flex-wrap gap-2 mb-3">
          {SUGGESTED.map((s) => (
            <button
              key={s}
              onClick={() => ask(s)}
              className="text-xs px-2.5 py-1 rounded-sm border border-ink-600 text-mist-300 hover:bg-ink-700"
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(question)}
            placeholder="Ask a question about this batch's finances…"
            className="flex-1 bg-ink-700 border border-ink-600 rounded-sm px-3 py-2 text-sm placeholder:text-mist-500"
          />
          <Button onClick={() => ask(question)} disabled={loading}>{loading ? "Asking…" : "Ask"}</Button>
        </div>
      </Panel>

      <div className="space-y-3">
        {history.map((h, i) => (
          <Panel key={i}>
            <div className="text-sm text-mist-300 mb-1">{h.question}</div>
            <div className="text-mist-100">{h.response.answer}</div>
            {h.response.supporting_records.length > 0 && (
              <div className="mt-2 text-xs text-mist-500 num">
                Supporting records: {h.response.supporting_records.slice(0, 10).map((r) => r.slice(0, 8)).join(", ")}
              </div>
            )}
            {h.response.confidence && (
              <div className="mt-1 text-xs text-mist-500">Confidence: {h.response.confidence}</div>
            )}
          </Panel>
        ))}
      </div>
    </div>
  );
}
