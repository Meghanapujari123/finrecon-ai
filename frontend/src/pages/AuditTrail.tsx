import { useEffect, useState } from "react";
import { api } from "../services/api";
import { Panel } from "../components/ui";
import type { AuditLogEntry } from "../types/api";

export default function AuditTrail() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);

  useEffect(() => {
    api.getAuditLogs().then(setLogs);
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-mist-100">Audit Trail</h1>
      <Panel title={`${logs.length} events`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-mist-500 text-xs uppercase border-b border-ink-600">
                <th className="py-2 pr-4">Timestamp</th>
                <th className="py-2 pr-4">Actor</th>
                <th className="py-2 pr-4">Action</th>
                <th className="py-2 pr-4">Entity</th>
                <th className="py-2 pr-4">Reason</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-ink-700/60">
                  <td className="py-2 pr-4 num text-xs text-mist-500">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="py-2 pr-4 text-mist-300">{log.actor}</td>
                  <td className="py-2 pr-4 num text-xs text-brand">{log.action}</td>
                  <td className="py-2 pr-4 num text-xs text-mist-500">{log.entity_type} · {log.entity_id.slice(0, 8)}</td>
                  <td className="py-2 pr-4 text-mist-500 text-xs max-w-xs truncate">{log.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.length === 0 && <div className="text-mist-500 text-sm py-6 text-center">No audit events yet.</div>}
        </div>
      </Panel>
    </div>
  );
}
