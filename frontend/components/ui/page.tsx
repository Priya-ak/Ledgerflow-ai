import { ChevronLeft, ChevronRight } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  return (
    <div className="flex items-center justify-between border-t px-4 py-3 text-xs text-muted-foreground">
      <span className="num">{from}–{Math.min(page * pageSize, total)} of {total}</span>
      <div className="flex items-center gap-1">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft /></Button>
        <span className="num px-2">{page} / {pages}</span>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight /></Button>
      </div>
    </div>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "default" | "warning" | "danger" | "success" }) {
  const color = tone === "warning" ? "text-warning" : tone === "danger" ? "text-danger" : tone === "success" ? "text-success" : "";
  return (
    <div className="rounded-xl border bg-surface px-4 py-3.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className={`num mt-1 text-xl font-semibold tracking-tight ${color}`}>{value}</p>
      {sub && <p className="num mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}
