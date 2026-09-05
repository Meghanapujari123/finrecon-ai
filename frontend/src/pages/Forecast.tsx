import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { useBatch } from "../hooks/useBatch";
import { api } from "../services/api";
import { Panel, StatTile, EmptyState } from "../components/ui";
import type { ForecastResult } from "../types/api";

export default function Forecast() {
  const { batch, reconciled } = useBatch();
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!batch) return;
    api.getForecast(batch.id, 7).then(setForecast).catch((e) => setError(e.message));
  }, [batch]);

  if (!batch) {
    return <EmptyState title="No dataset loaded" description="Load the demo dataset from the top bar to begin." />;
  }
  if (!reconciled) {
    return <EmptyState title="Reconciliation not run yet" description="The forecast uses reconciled payment history — run reconciliation first." />;
  }
  if (error) {
    return <EmptyState title="Forecast unavailable" description={error} />;
  }
  if (!forecast) {
    return <div className="text-mist-500 text-sm">Loading forecast…</div>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-mist-100">Cash Forecast — next {forecast.horizon_days} days</h1>

      <div className="grid grid-cols-3 gap-4">
        <StatTile label="Historical inflow" value={`₹${forecast.historical.total_inflow.toLocaleString("en-IN")}`} />
        <StatTile label="Historical outflow (fees)" value={`₹${forecast.historical.total_outflow.toLocaleString("en-IN")}`} />
        <StatTile label="Forecast confidence" value={forecast.confidence} tone={forecast.confidence === "HIGH" ? "good" : forecast.confidence === "LOW" ? "bad" : "gold"} />
      </div>

      <Panel title="Projected balance">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={forecast.projections}>
            <CartesianGrid stroke="#222C36" />
            <XAxis dataKey="forecast_date" stroke="#8B98A6" fontSize={11} />
            <YAxis stroke="#8B98A6" fontSize={11} />
            <Tooltip contentStyle={{ background: "#1B232C", border: "1px solid #2C3742", borderRadius: 4 }} />
            <Legend />
            <Line type="monotone" dataKey="predicted_balance" name="Projected balance" stroke="#5B8DEF" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="predicted_inflow" name="Predicted inflow" stroke="#3FB88F" strokeWidth={1.5} dot={false} />
            <Line type="monotone" dataKey="predicted_outflow" name="Predicted outflow" stroke="#E2685C" strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="Assumptions (forecast estimates, not guaranteed outcomes)">
        <ul className="text-sm text-mist-300 space-y-1 list-disc list-inside">
          {forecast.assumptions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
