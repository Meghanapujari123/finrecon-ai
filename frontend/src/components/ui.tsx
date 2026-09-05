import type { ReactNode } from "react";

export function Panel({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="bg-ink-800 border border-ink-600 rounded">
      {title && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-ink-600">
          <h2 className="text-sm font-semibold text-mist-100 tracking-tight">{title}</h2>
          {right}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

export function StatTile({
  label,
  value,
  sublabel,
  tone = "default",
}: {
  label: string;
  value: string;
  sublabel?: string;
  tone?: "default" | "good" | "bad" | "gold";
}) {
  const toneClass =
    tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : tone === "gold" ? "text-gold" : "text-mist-100";
  return (
    <div className="bg-ink-800 border border-ink-600 rounded p-4">
      <div className="text-xs text-mist-500 uppercase tracking-wide">{label}</div>
      <div className={`num text-2xl font-semibold mt-1 ${toneClass}`}>{value}</div>
      {sublabel && <div className="text-xs text-mist-500 mt-1">{sublabel}</div>}
    </div>
  );
}

const statusStyles: Record<string, string> = {
  MATCHED: "bg-good/15 text-good border-good/30",
  EXCEPTION: "bg-gold/15 text-gold border-gold/30",
  UNMATCHED: "bg-bad/15 text-bad border-bad/30",
  OPEN: "bg-gold/15 text-gold border-gold/30",
  UNDER_REVIEW: "bg-brand/15 text-brand border-brand/30",
  RESOLVED: "bg-good/15 text-good border-good/30",
  UNRESOLVED: "bg-bad/15 text-bad border-bad/30",
  REJECTED: "bg-mist-500/15 text-mist-500 border-mist-500/30",
  HIGH: "bg-bad/15 text-bad border-bad/30",
  MEDIUM: "bg-gold/15 text-gold border-gold/30",
  LOW: "bg-mist-500/15 text-mist-300 border-mist-500/30",
};

export function StatusBadge({ value }: { value: string }) {
  const cls = statusStyles[value] || "bg-mist-500/15 text-mist-300 border-mist-500/30";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-sm border text-xs font-medium ${cls}`}>
      {value.replace(/_/g, " ")}
    </span>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const base = "px-3 py-1.5 rounded-sm text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  const variants: Record<string, string> = {
    primary: "bg-brand text-white hover:bg-brand-dim",
    secondary: "bg-ink-700 text-mist-100 border border-ink-600 hover:bg-ink-600",
    danger: "bg-bad text-white hover:bg-bad-dim",
    ghost: "text-mist-300 hover:text-mist-100 hover:bg-ink-700",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${variants[variant]}`}>
      {children}
    </button>
  );
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="text-center py-16 px-4">
      <div className="text-mist-100 font-semibold">{title}</div>
      <div className="text-mist-500 text-sm mt-1 max-w-md mx-auto">{description}</div>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
