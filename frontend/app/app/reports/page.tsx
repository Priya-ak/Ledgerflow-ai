"use client";

import { Download, FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { RequirePermission } from "@/components/app/guard";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { download, errorMessage } from "@/lib/api";
import type { Page, Supplier } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

const REPORTS = [
  { key: "invoices", label: "Invoice register", desc: "One row per invoice with taxes, statuses and totals." },
  { key: "invoice-details", label: "Invoice line details", desc: "Every line item with HSN/SAC, quantities and tax." },
  { key: "suppliers", label: "Supplier report", desc: "Invoice counts, values and exceptions per supplier." },
  { key: "validation", label: "Validation exceptions", desc: "Every failed check with expected, actual and difference." },
  { key: "po-matching", label: "PO matching", desc: "Purchase-order comparison results and issues." },
  { key: "approvals", label: "Approval history", desc: "Submissions, decisions, approvers and comments." },
  { key: "monthly", label: "Monthly summary", desc: "Invoice count, total and approved value by month." },
];

interface Preview { title: string; columns: string[]; rows: (string | number | null)[][]; total_rows: number }

export default function ReportsPage() {
  const [kind, setKind] = useState("invoices");
  const [f, setF] = useState({ status: "", supplier_id: "", date_from: "", date_to: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const suppliers = useFetch<Page<Supplier>>("/suppliers", { page_size: 100 });
  const preview = useFetch<Preview>(`/reports/${kind}`, f);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  const exportOne = async (k: string) => {
    setBusy(k);
    try { await download(`/reports/${k}/export`, f); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };
  const exportAll = async () => {
    setBusy("all");
    try { await download("/reports/invoices/export", { ...f, include: REPORTS.map((r) => r.key).join(",") }); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(null); }
  };

  return (
    <RequirePermission perm="reports:export">
      <PageHeader title="Reports & export" description="Filter, preview and download Excel workbooks with formatted dates, currency and totals."
        actions={<Button onClick={exportAll} loading={busy === "all"}><FileSpreadsheet /> Export full workbook</Button>} />
      <Card className="mb-6">
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Invoice status"><Select value={f.status} onChange={set("status")}><option value="">All (excl. archived)</option><option value="approved">Approved</option><option value="pending_approval">Pending approval</option><option value="review_required">Needs review</option><option value="rejected">Rejected</option></Select></Field>
          <Field label="Supplier"><Select value={f.supplier_id} onChange={set("supplier_id")}><option value="">All suppliers</option>{suppliers.data?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
          <Field label="Invoice date from"><Input type="date" value={f.date_from} onChange={set("date_from")} /></Field>
          <Field label="Invoice date to"><Input type="date" value={f.date_to} onChange={set("date_to")} /></Field>
        </div>
      </Card>
      <div className="grid gap-6 xl:grid-cols-[320px_1fr]">
        <div className="space-y-2">
          {REPORTS.map((r) => (
            <div key={r.key} className={cn("flex items-start gap-2 rounded-xl border bg-surface p-3", kind === r.key && "border-primary ring-1 ring-primary")}>
              <button className="flex-1 text-left" onClick={() => setKind(r.key)}>
                <p className="text-sm font-medium">{r.label}</p><p className="text-xs text-muted-foreground">{r.desc}</p>
              </button>
              <Button size="icon" variant="ghost" aria-label={`Export ${r.label}`} onClick={() => exportOne(r.key)} loading={busy === r.key}>{busy !== r.key && <Download />}</Button>
            </div>
          ))}
        </div>
        <Card className="min-w-0">
          <CardHeader><div><CardTitle>{preview.data?.title ?? "Preview"}</CardTitle>{preview.data && <CardDescription>{preview.data.total_rows} rows{preview.data.total_rows > 500 ? " (showing first 500)" : ""}</CardDescription>}</div></CardHeader>
          {preview.error ? <ErrorState message={preview.error} onRetry={preview.reload} /> : !preview.data ? <div className="p-4"><Skeleton className="h-60" /></div> : (
            <div className="max-h-[60vh] overflow-auto">
              <Table>
                <THead><tr>{preview.data.columns.map((c) => <TH key={c}>{c}</TH>)}</tr></THead>
                <TBody>
                  {preview.data.rows.slice(0, 100).map((r, i) => <TR key={i}>{r.map((v, j) => <TD key={j} className="num whitespace-nowrap text-xs">{v ?? "—"}</TD>)}</TR>)}
                  {preview.data.rows.length === 0 && <tr><td className="px-4 py-8 text-center text-sm text-muted-foreground" colSpan={preview.data.columns.length}>No rows for these filters.</td></tr>}
                </TBody>
              </Table>
            </div>
          )}
        </Card>
      </div>
    </RequirePermission>
  );
}
