"use client";

import { AlertTriangle, CheckCircle2, CircleDashed, Info, XCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Callout, EmptyState } from "@/components/ui/feedback";
import { Field, Select, Textarea } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api, errorMessage, json } from "@/lib/api";
import type { AuditLog, Check, InvoiceDetail, Page, PurchaseOrder } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { cn, dateTime, humanize, money } from "@/lib/utils";

const SEV = {
  critical: { icon: XCircle, cls: "text-danger" },
  warning: { icon: AlertTriangle, cls: "text-warning" },
  info: { icon: Info, cls: "text-info" },
};

export function ValidationPanel({ inv }: { inv: InvoiceDetail }) {
  const [showPassed, setShowPassed] = useState(false);
  const v = inv.validation;
  if (!v) return <Card><EmptyState icon={CircleDashed} title="Validation has not run yet" /></Card>;
  const failed = v.checks.filter((c) => !c.passed).sort((a, b) => order(a) - order(b));
  const passed = v.checks.filter((c) => c.passed);
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Financial validation</CardTitle>
          <CardDescription className="num">{v.summary.passed}/{v.summary.total} checks passed · {v.summary.critical_failures} critical · {v.summary.warnings} warnings · tolerance ₹{v.tolerance.amount} (lines ₹{v.tolerance.line})</CardDescription>
        </div>
        <StatusBadge value={v.status} />
      </CardHeader>
      <ul className="divide-y">
        {failed.map((c, i) => <CheckRow key={`${c.code}-${i}`} c={c} />)}
        {failed.length === 0 && <li className="flex items-center gap-2 px-5 py-4 text-sm text-success"><CheckCircle2 className="size-4" /> All checks passed.</li>}
      </ul>
      <div className="border-t px-5 py-3">
        <button className="text-xs font-medium text-primary hover:underline" onClick={() => setShowPassed(!showPassed)}>{showPassed ? "Hide" : "Show"} {passed.length} passed checks</button>
      </div>
      {showPassed && <ul className="divide-y border-t">{passed.map((c, i) => <CheckRow key={`p-${c.code}-${i}`} c={c} />)}</ul>}
      <p className="border-t px-5 py-2 text-[11px] text-muted-foreground">Calculated by the deterministic decimal engine ({dateTime(v.generated_at)}). GSTIN checks are format checks only.</p>
    </Card>
  );
}

function order(c: Check) {
  return c.severity === "critical" ? 0 : c.severity === "warning" ? 1 : 2;
}

function CheckRow({ c }: { c: Check }) {
  const { icon: Icon, cls } = c.passed ? { icon: CheckCircle2, cls: "text-success" } : SEV[c.severity];
  return (
    <li className="flex gap-3 px-5 py-3" data-testid={`check-${c.code}`}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", cls)} />
      <div className="min-w-0 flex-1 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{c.name}</span>
          {c.line_no && <Badge>Line {c.line_no}</Badge>}
          {!c.passed && <Badge tone={c.severity === "critical" ? "danger" : c.severity === "warning" ? "warning" : "info"}>{c.severity}</Badge>}
        </div>
        <p className="mt-0.5 text-muted-foreground">{c.explanation}</p>
        {(c.expected || c.actual) && !c.passed && (
          <dl className="num mt-1.5 flex flex-wrap gap-x-5 gap-y-1 text-xs">
            {c.expected && <div><dt className="inline text-muted-foreground">Expected </dt><dd className="inline font-medium">{c.expected}</dd></div>}
            {c.actual && <div><dt className="inline text-muted-foreground">Actual </dt><dd className="inline font-medium">{c.actual}</dd></div>}
            {c.difference && <div><dt className="inline text-muted-foreground">Difference </dt><dd className="inline font-medium text-danger">{c.difference}</dd></div>}
          </dl>
        )}
        {c.recommended_action && !c.passed && <p className="mt-1 text-xs text-foreground/80">→ {c.recommended_action}</p>}
      </div>
    </li>
  );
}

export function PoMatchPanel({ inv, editable, onChange }: { inv: InvoiceDetail; editable: boolean; onChange: (i: InvoiceDetail) => void }) {
  const pos = useFetch<Page<PurchaseOrder>>(editable ? "/purchase-orders" : null, { page_size: 100 });
  const [poId, setPoId] = useState(inv.purchase_order_id ?? "");
  const [busy, setBusy] = useState(false);
  const r = inv.po_match;
  const rematch = async () => {
    setBusy(true);
    try { onChange(await api<InvoiceDetail>(`/invoices/${inv.id}/match-purchase-order`, { method: "POST", body: json({ purchase_order_id: poId || null }) })); toast.success("PO matching updated"); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Card>
      <CardHeader>
        <div><CardTitle>Purchase-order matching</CardTitle><CardDescription>{r?.purchase_order ? `Compared with ${r.purchase_order.po_number}` : "No purchase order linked"}</CardDescription></div>
        <StatusBadge value={inv.po_match_status} />
      </CardHeader>
      {editable && (
        <div className="flex flex-wrap items-end gap-2 border-b px-5 py-3">
          <Field label="Match against" className="min-w-60 flex-1">
            <Select value={poId} onChange={(e) => setPoId(e.target.value)}><option value="">PO number printed on invoice</option>{pos.data?.items.map((p) => <option key={p.id} value={p.id}>{p.po_number} · {p.supplier.name} · {money(p.total_amount)}</option>)}</Select>
          </Field>
          <Button variant="outline" onClick={rematch} loading={busy}>Run matching</Button>
        </div>
      )}
      {r && (
        <CardContent className="space-y-4">
          {r.issues.length > 0 && <Callout tone={inv.po_match_status === "matched" ? "info" : "warning"}><ul className="list-disc space-y-0.5 pl-4">{r.issues.map((i) => <li key={i}>{i}</li>)}</ul></Callout>}
          {r.matched_items.length > 0 && (
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <THead><tr><TH>Invoice line</TH><TH>PO line</TH><TH>Field</TH><TH className="text-right">Invoice</TH><TH className="text-right">PO</TH><TH className="text-right">Difference</TH></tr></THead>
                <TBody>
                  {r.matched_items.flatMap((m) => m.differences.length ? m.differences.map((d, j) => (
                    <TR key={`${m.invoice_line}-${d.field}`}>
                      {j === 0 && <TD rowSpan={m.differences.length} className="align-top"><span className="font-medium">{m.invoice_line}.</span> {m.description}</TD>}
                      {j === 0 && <TD rowSpan={m.differences.length} className="align-top text-muted-foreground">{m.po_line}. {m.po_description}</TD>}
                      <TD>{humanize(d.field)}</TD><TD className="num text-right">{d.invoice}</TD><TD className="num text-right">{d.po}</TD><TD className="num text-right font-medium text-danger">{d.difference ?? "—"}</TD>
                    </TR>
                  )) : [(
                    <TR key={m.invoice_line}><TD><span className="font-medium">{m.invoice_line}.</span> {m.description}</TD><TD className="text-muted-foreground">{m.po_line}. {m.po_description}</TD><TD colSpan={4}><span className="inline-flex items-center gap-1 text-success"><CheckCircle2 className="size-3.5" /> Matches</span></TD></TR>
                  )])}
                </TBody>
              </Table>
            </div>
          )}
          {r.extra_items.length > 0 && <div><p className="text-xs font-medium text-muted-foreground">Not on the PO</p><ul className="mt-1 text-sm">{r.extra_items.map((e) => <li key={e.invoice_line}>Line {e.invoice_line}: {e.description} <span className="num text-muted-foreground">({money(e.amount)})</span></li>)}</ul></div>}
          {r.missing_items.length > 0 && <div><p className="text-xs font-medium text-muted-foreground">Ordered but not invoiced</p><ul className="mt-1 text-sm">{r.missing_items.map((e) => <li key={e.po_line}>PO line {e.po_line}: {e.description} × {e.quantity}</li>)}</ul></div>}
          {r.totals && <p className="num text-sm text-muted-foreground">Invoice {money(r.totals.invoice)} vs PO {money(r.totals.po)} · difference <span className={r.totals.within_tolerance ? "" : "font-medium text-danger"}>{money(r.totals.difference)}</span></p>}
        </CardContent>
      )}
    </Card>
  );
}

export function DuplicatesPanel({ inv, canResolve, onChange }: { inv: InvoiceDetail; canResolve: boolean; onChange: (i: InvoiceDetail) => void }) {
  const [target, setTarget] = useState<string | null>(null);
  const [resolution, setResolution] = useState("not_duplicate");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const resolve = async () => {
    setBusy(true);
    try {
      onChange(await api<InvoiceDetail>(`/invoices/${inv.id}/duplicates/${target}/resolve`, { method: "POST", body: json({ resolution, note }) }));
      toast.success("Duplicate decision recorded"); setTarget(null); setNote("");
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Card>
      <CardHeader><div><CardTitle>Duplicate detection</CardTitle><CardDescription>Supplier, invoice number, amount, date and file checksum are compared.</CardDescription></div><StatusBadge value={inv.duplicate_status} /></CardHeader>
      {inv.duplicates.length === 0 ? <CardContent className="text-sm text-muted-foreground">No similar invoices found.</CardContent> : (
        <ul className="divide-y">
          {inv.duplicates.map((d) => (
            <li key={d.id} className="px-5 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={d.match_type === "probable" ? "warning" : "danger"}>{humanize(d.match_type)}</Badge>
                <span className="num text-xs text-muted-foreground">score {d.score}</span>
                <Link href={`/app/invoices/${d.matched_invoice_id}`} className="text-primary hover:underline">Open matching invoice</Link>
                {d.resolution && <Badge tone="success">{humanize(d.resolution)}</Badge>}
                {canResolve && !d.resolution && <Button size="sm" variant="outline" className="ml-auto" onClick={() => setTarget(d.id)}>Resolve</Button>}
              </div>
              <ul className="mt-1.5 list-disc pl-5 text-muted-foreground">{d.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              {d.resolution_note && <p className="mt-1 text-xs">Note: {d.resolution_note}</p>}
            </li>
          ))}
        </ul>
      )}
      <Dialog open={!!target} onOpenChange={(o) => !o && setTarget(null)}>
        <DialogContent title="Resolve duplicate warning" description="Your decision and note are recorded in the audit log.">
          <div className="space-y-4">
            <Field label="Decision"><Select value={resolution} onChange={(e) => setResolution(e.target.value)}><option value="not_duplicate">Not a duplicate — keep processing</option><option value="confirmed_duplicate">Confirmed duplicate — do not pay</option></Select></Field>
            <Field label="Reason" hint="At least 5 characters"><Textarea value={note} onChange={(e) => setNote(e.target.value)} /></Field>
            <div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setTarget(null)}>Cancel</Button><Button onClick={resolve} loading={busy} disabled={note.trim().length < 5}>Save decision</Button></div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

export function ApprovalHistory({ inv }: { inv: InvoiceDetail }) {
  if (inv.approvals.length === 0) return <Card><EmptyState icon={CircleDashed} title="Not submitted yet" description="Submit the invoice once review is complete." /></Card>;
  return (
    <div className="space-y-4">
      {inv.approvals.map((a) => (
        <Card key={a.id}>
          <CardHeader>
            <div><CardTitle>Approval request</CardTitle><CardDescription>Submitted {dateTime(a.created_at)}{a.submission_note ? ` · “${a.submission_note}”` : ""}</CardDescription></div>
            <StatusBadge value={a.status} />
          </CardHeader>
          <CardContent>
            <ol className="space-y-3">
              {a.required_levels.map((lv) => {
                const step = a.steps.find((s) => s.level === lv.level);
                const current = a.status === "pending" && a.current_level === lv.level;
                return (
                  <li key={lv.level} className="flex gap-3 text-sm">
                    <span className={cn("num mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                      step?.decision === "approved" ? "bg-success-soft text-success" : step?.decision === "rejected" ? "bg-danger-soft text-danger" : current ? "bg-info-soft text-info" : "bg-surface-muted text-muted-foreground")}>{lv.level}</span>
                    <div>
                      <p className="font-medium">{lv.name} <span className="font-normal text-muted-foreground">· {humanize(lv.role)}{Number(lv.min_amount) > 0 ? ` · from ${money(lv.min_amount)}` : ""}</span></p>
                      {step ? <p className="text-muted-foreground">{humanize(step.decision)} {dateTime(step.created_at)}{step.comment ? ` — “${step.comment}”` : ""}{step.override_critical ? " (critical-error override)" : ""}</p>
                        : <p className="text-muted-foreground">{current ? "Waiting for decision" : a.status === "pending" ? "Not reached yet" : "—"}</p>}
                    </div>
                  </li>
                );
              })}
            </ol>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function ActivityPanel({ invoiceId }: { invoiceId: string }) {
  const { data } = useFetch<AuditLog[]>(`/audit-logs/entity/${invoiceId}`);
  return (
    <Card>
      <CardHeader><CardTitle>Activity</CardTitle></CardHeader>
      {!data ? <CardContent className="text-sm text-muted-foreground">Loading…</CardContent> : (
        <ol className="divide-y">
          {data.map((a) => (
            <li key={a.id} className="px-5 py-2.5 text-sm">
              <div className="flex justify-between gap-3"><span className="font-medium">{humanize(a.action.replace("invoice.", ""))}</span><span className="num shrink-0 text-xs text-muted-foreground">{dateTime(a.created_at)}</span></div>
              <p className="text-xs text-muted-foreground">{a.actor_email ?? "system"}{summarise(a.meta)}</p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function summarise(meta: Record<string, unknown> | null): string {
  if (!meta) return "";
  if (meta.changes && typeof meta.changes === "object") {
    const keys = Object.keys(meta.changes as object);
    return keys.length ? ` · changed ${keys.slice(0, 6).map(humanize).join(", ")}${keys.length > 6 ? "…" : ""}` : "";
  }
  if (meta.reason) return ` · “${meta.reason}”`;
  if (meta.validation_status) return ` · validation ${meta.validation_status}`;
  return "";
}
