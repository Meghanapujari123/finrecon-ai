export interface Batch {
  id: string;
  label: string;
  source: string;
  seed: string | null;
  created_at: string;
}

export interface ReconciliationRunResult {
  batch_id: string;
  total_records: number;
  matched: number;
  unmatched: number;
  exceptions: number;
  match_rate: number;
  processing_time_ms: number;
  throughput_records_per_second: number;
  error?: string | null;
}

export interface ReconciliationResultRow {
  id: string;
  batch_id: string;
  payment_id: string | null;
  bank_transaction_id: string | null;
  ledger_entry_id: string | null;
  match_status: string;
  match_method: string;
  confidence: number;
  amount_difference: number;
  date_difference_days: number;
  reason: string;
}

export interface ExceptionRecord {
  id: string;
  batch_id: string;
  exception_type: string;
  severity: string;
  payment_id: string | null;
  bank_transaction_id: string | null;
  ledger_entry_id: string | null;
  amount_affected: number;
  description: string;
  status: string;
  ai_analysis: Record<string, unknown> | null;
  ai_confidence: number | null;
  ai_root_cause: string | null;
  ai_status: string;
  recommended_action: string | null;
  risk_level: string | null;
  requires_human_approval: boolean;
  created_at: string;
  resolved_at: string | null;
}

export interface DashboardSummary {
  batch_id: string;
  total_records: number;
  matched: number;
  exceptions: number;
  match_rate: number;
  accuracy: number | null;
  throughput_records_per_second: number | null;
  amount_affected: number;
  human_review_required: number;
}

export interface EvaluationResult {
  batch_id: string;
  dataset_size: number;
  match_accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  false_positive_count: number;
  false_negative_count: number;
  false_match_count: number;
  exception_classification_accuracy: number;
  unresolved_exception_count: number;
  open_exception_count: number;
  resolved_exception_count: number;
  total_exceptions: number;
  amount_affected_total: number;
  amount_correctly_reconciled: number;
  evaluation_processing_time_ms: number;
}

export interface AuditLogEntry {
  id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  previous_state: Record<string, unknown> | null;
  new_state: Record<string, unknown> | null;
  reason: string | null;
  timestamp: string;
}

export interface QAResponse {
  answer: string;
  supporting_records: string[];
  calculated_metrics: Record<string, unknown>;
  confidence: string | null;
}

export interface ForecastProjection {
  forecast_date: string;
  predicted_inflow: number;
  predicted_outflow: number;
  predicted_net: number;
  predicted_balance: number;
}

export interface ForecastResult {
  batch_id: string;
  horizon_days: number;
  confidence: string;
  assumptions: string[];
  historical: { total_inflow: number; total_outflow: number; days_of_data: number };
  projections: ForecastProjection[];
}
