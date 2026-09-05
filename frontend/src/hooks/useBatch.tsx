import { createContext, useContext, useState, type ReactNode } from "react";
import type { Batch } from "../types/api";

interface BatchContextValue {
  batch: Batch | null;
  setBatch: (b: Batch | null) => void;
  reconciled: boolean;
  setReconciled: (v: boolean) => void;
}

const BatchContext = createContext<BatchContextValue | undefined>(undefined);

export function BatchProvider({ children }: { children: ReactNode }) {
  const [batch, setBatch] = useState<Batch | null>(null);
  const [reconciled, setReconciled] = useState(false);

  return (
    <BatchContext.Provider value={{ batch, setBatch, reconciled, setReconciled }}>
      {children}
    </BatchContext.Provider>
  );
}

export function useBatch() {
  const ctx = useContext(BatchContext);
  if (!ctx) throw new Error("useBatch must be used within BatchProvider");
  return ctx;
}
