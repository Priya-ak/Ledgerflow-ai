import { AlertTriangle, CheckCircle2, Info, XCircle, type LucideIcon } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-surface-muted", className)} />;
}

export function EmptyState({ icon: Icon, title, description, action }: { icon: LucideIcon; title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 rounded-full bg-surface-muted p-3"><Icon className="size-5 text-muted-foreground" /></div>
      <p className="text-sm font-medium">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

const CALLOUT = {
  info: { icon: Info, cls: "bg-info-soft text-info border-info/20" },
  success: { icon: CheckCircle2, cls: "bg-success-soft text-success border-success/20" },
  warning: { icon: AlertTriangle, cls: "bg-warning-soft text-warning border-warning/25" },
  danger: { icon: XCircle, cls: "bg-danger-soft text-danger border-danger/20" },
};

export function Callout({ tone = "info", title, children, className }: { tone?: keyof typeof CALLOUT; title?: string; children?: React.ReactNode; className?: string }) {
  const { icon: Icon, cls } = CALLOUT[tone];
  return (
    <div className={cn("flex gap-3 rounded-lg border px-4 py-3 text-sm", cls, className)} role={tone === "danger" ? "alert" : "status"}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 space-y-0.5">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="text-foreground/80">{children}</div>}
      </div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Callout tone="danger" title="Could not load data" className="m-4">
      <span>{message}</span>
      {onRetry && <button onClick={onRetry} className="ml-2 font-medium underline">Retry</button>}
    </Callout>
  );
}
