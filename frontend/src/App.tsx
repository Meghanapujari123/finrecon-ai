import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "./layouts/AppShell";
import { BatchProvider } from "./hooks/useBatch";
import Overview from "./pages/Overview";
import Reconciliation from "./pages/Reconciliation";
import Exceptions from "./pages/Exceptions";
import QA from "./pages/QA";
import Forecast from "./pages/Forecast";
import AuditTrail from "./pages/AuditTrail";
import Evaluation from "./pages/Evaluation";

export default function App() {
  return (
    <BatchProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Overview />} />
            <Route path="/reconciliation" element={<Reconciliation />} />
            <Route path="/exceptions" element={<Exceptions />} />
            <Route path="/qa" element={<QA />} />
            <Route path="/forecast" element={<Forecast />} />
            <Route path="/audit" element={<AuditTrail />} />
            <Route path="/evaluation" element={<Evaluation />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </BatchProvider>
  );
}
