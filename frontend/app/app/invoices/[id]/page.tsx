"use client";

import { Archive, ArrowLeft, Check, ChevronLeft, ChevronRight, Download, RefreshCw, Send, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { ActivityPanel, ApprovalHistory, DuplicatesPanel, PoMatchPanel, ValidationPanel } from "@/components/app/invoice-panels";
import { InvoiceForm, toFormValues, toPayload, type InvoiceFormValues } from "@/components/app/invoice-form";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Callout, EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Textarea } from "@/components/ui/input";
import { api, download, errorMessage, json } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { InvoiceDetail } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { cn, money } from "@/lib/utils";
import { FileX } from "lucide-react";

const EDITABLE = ["draft", "extracted", "review_required", "failed_processing", "rejected"];
const TABS = ["details", "validation", "po", "duplicates", "approvals", "activity"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABEL: Record<Tab, string> = { details: "Details", validation: "Validation", po: "PO match", duplicates: "Duplicates", approvals: "Approvals", activity: "Activity" };

export default function InvoicePage() {
  const { id } = useParams<{ id: string }>();
  const { me, can } = useSession();
  const { data: inv, error, setData, reload } = useFetch<InvoiceDetail>(`/invoices/${id}`);
  const [tab, setTab] = useState<Tab>("details");
  const [dialog, setDialog] = useState<null | "submit" | "approve" | "reject" | "archive">(null);
  const [text, setText] = useState("");
  const [override, setOverride] = useState(false);
  const [busy, setBusy] = useState(false);

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!inv || !me) return <div className="space-y-4"><Skeleton className="h-12" /><Skeleton className="h-[70vh]" /></div>;

  const editable = EDITABLE.includes(inv.status) && can("invoices:write");
  const pending = inv.approvals.find((a) => a.status === "pending");
  const level = pending?.required_levels.find((l) => l.level === pending.current_level);
  const canDecide = !!pending && can("approvals:decide") && pending.submitted_by_id !== me.user.id
    && (me.user.role === "admin" || me.user.role === level?.role) && !pending.steps.some((s) => s.approver_id === me.user.id && s.decision === "approved");
  const canSubmit = editable && can("invoices:submit") && inv.status !== "failed_processing";
  const failedChecks = inv.validation?.checks.filter((c) => !c.passed && c.severity !== "info").length ?? 0;
  const meta = inv.extracted_data?.extraction_metadata;

  const act = async (fn: () => Promise<InvoiceDetail>, ok: string) => {
    setBusy(true);
    try { setData(await fn()); toast.success(ok); setDialog(null); setText(""); setOverride(false); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const save = async (v: InvoiceFormValues) => {
    try {
      const updated = await api<InvoiceDetail>(`/invoices/${inv.id}`, { method: "PUT", body: json(toPayload(v)) });
      setData(updated);
      toast.success(`Saved · validation ${updated.validation_status.replace("_", " ")}`);
    } catch (e) { toast.error(errorMessage(e)); }
  };

  return (
    <>
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <Link href="/app/invoices" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"><ArrowLeft className="size-3.5" /> Invoices</Link>
          <h1 className="mt-1 text-xl font-semibold tracking-tight" data-testid="invoice-title">{inv.invoice_number ?? "Untitled invoice"}
            <span className="ml-2 font-normal text-muted-foreground">{inv.supplier?.name ?? inv.supplier_name_raw ?? ""}</span></h1>
          <div className="mt-2 flex flex-wrap items-center gap-2" data-testid="invoice-status">
            <StatusBadge value={inv.status} /><StatusBadge value={inv.validation_status} /><StatusBadge value={inv.duplicate_status} /><StatusBadge value={inv.po_match_status} />
            <span className="num ml-1 text-sm font-semibold">{money(inv.grand_total)}</span>
            {inv.is_demo && <span className="text-xs text-muted-foreground">· demo record</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {editable && <Button variant="outline" onClick={() => act(() => api(`/invoices/${inv.id}/validate`, { method: "POST" }), "Checks re-run")} loading={busy && !dialog}><RefreshCw /> Re-run checks</Button>}
          {canSubmit && <Button onClick={() => setDialog("submit")} data-testid="submit-btn"><Send /> Submit for approval</Button>}
          {canDecide && <Button variant="danger" onClick={() => setDialog("reject")} data-testid="reject-btn"><X /> Reject</Button>}
          {canDecide && <Button variant="success" onClick={() => setDialog("approve")} data-testid="approve-btn"><Check /> Approve</Button>}
          {can("invoices:delete") && !["archived", "pending_approval"].includes(inv.status) && <Button variant="ghost" onClick={() => setDialog("archive")} aria-label="Archive invoice"><Archive /></Button>}
        </div>
      </div>

      {inv.status === "failed_processing" && <Callout tone="danger" title="Processing failed" className="mb-4">{inv.documents[0]?.error_message ?? "The document could not be read."} You can enter the details manually below.</Callout>}
      {inv.has_critical_errors && inv.status !== "approved" && <Callout tone="danger" className="mb-4" title="Critical validation errors">This invoice cannot be approved until the critical issues on the Validation tab are corrected.</Callout>}
      {meta && meta.warnings.length > 0 && EDITABLE.includes(inv.status) && (
        <Callout tone="warning" className="mb-4" title={`Extraction notes (${meta.method}${meta.text_method ? `, ${meta.text_method.replace("_", " ")}` : ""}${meta.ocr_confidence != null ? `, OCR ${meta.ocr_confidence}%` : ""})`}>
          <ul className="list-disc pl-4">{meta.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </Callout>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(380px,0.85fr)_1.4fr]">
        <DocumentPreview inv={inv} />
        <div className="min-w-0">
          <div className="mb-4 flex gap-1 overflow-x-auto border-b" role="tablist">
            {TABS.map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                className={cn("-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm", tab === t ? "border-primary font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}>
                {TAB_LABEL[t]}
                {t === "validation" && failedChecks > 0 && <span className="num ml-1.5 rounded-full bg-danger-soft px-1.5 text-xs text-danger">{failedChecks}</span>}
                {t === "duplicates" && inv.duplicates.filter((d) => !d.resolution).length > 0 && <span className="num ml-1.5 rounded-full bg-warning-soft px-1.5 text-xs text-warning">{inv.duplicates.filter((d) => !d.resolution).length}</span>}
              </button>
            ))}
          </div>
          {tab === "details" && <InvoiceForm formId="invoice-form" initial={toFormValues(inv)} readOnly={!editable} reviewFields={inv.needs_review_fields ?? []} onSubmit={save} submitLabel="Save corrections" />}
          {tab === "validation" && <ValidationPanel inv={inv} />}
          {tab === "po" && <PoMatchPanel inv={inv} editable={editable} onChange={setData} />}
          {tab === "duplicates" && <DuplicatesPanel inv={inv} canResolve={can("duplicates:resolve") && EDITABLE.includes(inv.status)} onChange={setData} />}
          {tab === "approvals" && <ApprovalHistory inv={inv} />}
          {tab === "activity" && <ActivityPanel invoiceId={inv.id} />}
        </div>
      </div>

      <Dialog open={dialog === "submit"} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent title="Submit for approval" description="The latest checks run again before submission. The invoice is locked while pending.">
          {inv.validation_status !== "passed" && <Callout tone="warning" className="mb-4">Validation status is “{inv.validation_status}”. Approvers will see every open issue.</Callout>}
          <Field label="Note for approver (optional)"><Textarea value={text} onChange={(e) => setText(e.target.value)} /></Field>
          <div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={() => setDialog(null)}>Cancel</Button>
            <Button loading={busy} data-testid="confirm-submit" onClick={() => act(() => api(`/invoices/${inv.id}/submit`, { method: "POST", body: json({ note: text || null }) }), "Submitted for approval")}>Submit</Button></div>
        </DialogContent>
      </Dialog>

      <Dialog open={dialog === "approve"} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent title={`Approve ${level ? `— ${level.name}` : ""}`} description={`${money(inv.grand_total)} · ${inv.supplier?.name ?? ""}`}>
          {inv.has_critical_errors && <Callout tone="danger" className="mb-4">This invoice has critical validation errors. Approval is blocked unless your company policy allows an admin override with a written justification.</Callout>}
          <Field label={inv.has_critical_errors ? "Justification" : "Comment (optional)"}><Textarea value={text} onChange={(e) => setText(e.target.value)} /></Field>
          {inv.has_critical_errors && me.user.role === "admin" && (
            <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={override} onChange={(e) => setOverride(e.target.checked)} /> Override critical errors (recorded in audit log)</label>
          )}
          <div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={() => setDialog(null)}>Cancel</Button>
            <Button variant="success" loading={busy} data-testid="confirm-approve" onClick={() => act(() => api(`/invoices/${inv.id}/approve`, { method: "POST", body: json({ comment: text || null, override_critical: override }) }), "Approved")}>Approve</Button></div>
        </DialogContent>
      </Dialog>

      <Dialog open={dialog === "reject"} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent title="Reject invoice" description="The accountant will see your reason and can correct and resubmit.">
          <Field label="Reason for rejection" hint="Required, at least 5 characters"><Textarea data-testid="reject-reason" value={text} onChange={(e) => setText(e.target.value)} /></Field>
          <div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={() => setDialog(null)}>Cancel</Button>
            <Button variant="danger" loading={busy} disabled={text.trim().length < 5} data-testid="confirm-reject" onClick={() => act(() => api(`/invoices/${inv.id}/reject`, { method: "POST", body: json({ reason: text }) }), "Rejected")}>Reject</Button></div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog open={dialog === "archive"} onOpenChange={(o) => !o && setDialog(null)} title="Archive this invoice?" confirmLabel="Archive"
        description="Archived invoices are hidden from lists and analytics but retained with their documents and audit history."
        onConfirm={() => act(() => api(`/invoices/${inv.id}`, { method: "DELETE" }), "Invoice archived")} />
    </>
  );
}

function DocumentPreview({ inv }: { inv: InvoiceDetail }) {
  const doc = inv.documents[0];
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(false);
  const pages = doc?.page_count ?? 1;
  return (
    <Card className="xl:sticky xl:top-20 xl:self-start">
      <CardHeader>
        <CardTitle className="truncate">{doc ? doc.original_filename : "Original document"}</CardTitle>
        {doc && (
          <div className="flex shrink-0 items-center gap-1">
            {pages > 1 && (
              <>
                <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft /></Button>
                <span className="num text-xs text-muted-foreground">{page}/{pages}</span>
                <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight /></Button>
              </>
            )}
            <Button size="sm" variant="ghost" asChild><a href={`/api/v1/documents/${doc.id}/download`} target="_blank" rel="noopener">Open original</a></Button>
            <Button size="icon" variant="ghost" aria-label="Download original" onClick={() => download(`/documents/${doc.id}/download`, { inline: false }).catch((e) => toast.error(errorMessage(e)))}><Download /></Button>
          </div>
        )}
      </CardHeader>
      {!doc ? <EmptyState icon={FileX} title="No document attached" description="This invoice was entered manually." /> : (
        <div className="max-h-[75vh] overflow-auto rounded-b-xl bg-surface-muted">
          {/* Server-rendered page image: identical in every browser, small and memory-friendly. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img key={page} src={`/api/v1/documents/${doc.id}/preview?page=${page}`} alt={`Invoice page ${page}`} onClick={() => setZoom(!zoom)}
            className={cn("mx-auto bg-white", zoom ? "w-[160%] max-w-none cursor-zoom-out" : "w-full cursor-zoom-in")} data-testid="document-preview" />
        </div>
      )}
    </Card>
  );
}
