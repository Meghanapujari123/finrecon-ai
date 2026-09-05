const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),

  listBatches: () => request<import("../types/api").Batch[]>("/api/batches"),
  loadDemoBatch: (nBase = 150, seed = 42) =>
    request<import("../types/api").Batch>(`/api/batches/demo?n_base=${nBase}&seed=${seed}`, { method: "POST" }),
  uploadCsv: (label: string, form: FormData) =>
    fetch(`${BASE_URL}/api/batches/upload?label=${encodeURIComponent(label)}`, {
      method: "POST",
      body: form,
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || res.statusText);
      }
      return res.json();
    }),

  runReconciliation: (batchId: string) =>
    request<import("../types/api").ReconciliationRunResult>(`/api/reconciliation/run/${batchId}`, {
      method: "POST",
    }),
  getReconciliationResults: (batchId: string) =>
    request<import("../types/api").ReconciliationResultRow[]>(`/api/reconciliation/results/${batchId}`),

  listExceptions: (batchId: string, filters?: Record<string, string>) => {
    const params = new URLSearchParams({ batch_id: batchId, ...filters });
    return request<import("../types/api").ExceptionRecord[]>(`/api/exceptions?${params.toString()}`);
  },
  investigateException: (id: string) =>
    request<import("../types/api").ExceptionRecord>(`/api/exceptions/${id}/investigate`, { method: "POST" }),
  resolveException: (id: string, action: string, actor: string, reason?: string) =>
    request<import("../types/api").ExceptionRecord>(`/api/exceptions/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ action, actor, reason }),
    }),

  getDashboard: (batchId: string) =>
    request<import("../types/api").DashboardSummary>(`/api/dashboard/${batchId}`),
  runEvaluation: (batchId: string) =>
    request<import("../types/api").EvaluationResult>(`/api/evaluation/run?batch_id=${batchId}`, {
      method: "POST",
    }),
  getAuditLogs: () => request<import("../types/api").AuditLogEntry[]>("/api/audit"),
  askQuestion: (batchId: string, question: string) =>
    request<import("../types/api").QAResponse>("/api/qa/ask", {
      method: "POST",
      body: JSON.stringify({ batch_id: batchId, question }),
    }),
  getForecast: (batchId: string, horizonDays = 7) =>
    request<import("../types/api").ForecastResult>(`/api/forecast/${batchId}?horizon_days=${horizonDays}`),
};
