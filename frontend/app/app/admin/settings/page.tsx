"use client";

import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { RequirePermission } from "@/components/app/guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Callout, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page";
import { api, errorMessage, json } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Company } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";

interface Settings { currency: string; amount_tolerance: string; po_price_tolerance_pct: string; po_qty_tolerance_pct: string; duplicate_window_days: number; require_mfa: boolean; notify_approvers: boolean }
interface Level { level: number; name: string; role: "approver" | "admin"; min_amount: string }
interface Policy { levels: Level[]; allow_self_approval: boolean; allow_critical_override: boolean }
interface SystemStatus {
  environment: string; database: string; storage: string; demo_mode: boolean; ocr: { engine: string; available: boolean };
  ai: { provider: string; available: boolean; model: string | null; detail: string }; limits: { max_upload_mb: number; max_pdf_pages: number };
  malware_scanning: { pdf_active_content_policy: boolean; engine: string; available: boolean | null; version: string | null; fail_closed: boolean };
  email: { provider: string; from: string };
}

export default function SettingsPage() {
  return (
    <RequirePermission perm="settings:manage">
      <PageHeader title="Company & policy" description="Company profile, validation tolerances and the approval policy." />
      <div className="grid gap-6 xl:grid-cols-2">
        <CompanyCard />
        <SystemCard />
        <ToleranceCard />
        <SecurityCard />
        <PolicyCard />
      </div>
    </RequirePermission>
  );
}

function CompanyCard() {
  const { refresh } = useSession();
  const { data, setData } = useFetch<Company>("/company");
  const [busy, setBusy] = useState(false);
  if (!data) return <Skeleton className="h-72" />;
  const set = (k: keyof Company) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setData({ ...data, [k]: e.target.value });
  return (
    <Card>
      <CardHeader><div><CardTitle>Company profile</CardTitle><CardDescription>Your GSTIN determines intra- vs inter-state GST checks.</CardDescription></div></CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <Field label="Company name" className="sm:col-span-2"><Input value={data.name} onChange={set("name")} /></Field>
        <Field label="GSTIN"><Input className="uppercase" maxLength={15} value={data.gstin ?? ""} onChange={set("gstin")} /></Field>
        <Field label="Phone"><Input value={data.phone ?? ""} onChange={set("phone")} /></Field>
        <Field label="Email" className="sm:col-span-2"><Input type="email" value={data.email ?? ""} onChange={set("email")} /></Field>
        <Field label="Address" className="sm:col-span-2"><Textarea rows={2} value={data.address ?? ""} onChange={set("address")} /></Field>
        <div className="sm:col-span-2 flex justify-end"><Button loading={busy} onClick={async () => {
          setBusy(true);
          try { setData(await api<Company>("/company", { method: "PUT", body: json({ name: data.name, gstin: data.gstin || null, address: data.address || null, email: data.email || null, phone: data.phone || null }) })); toast.success("Company updated"); void refresh(); }
          catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
        }}>Save profile</Button></div>
      </CardContent>
    </Card>
  );
}

function ToleranceCard() {
  const { data, setData } = useFetch<Settings>("/company/settings");
  const [busy, setBusy] = useState(false);
  if (!data) return <Skeleton className="h-72" />;
  const set = (k: keyof Settings) => (e: React.ChangeEvent<HTMLInputElement>) => setData({ ...data, [k]: e.target.value });
  return (
    <Card>
      <CardHeader><div><CardTitle>Validation & matching tolerances</CardTitle><CardDescription>Differences within tolerance pass; larger differences are flagged.</CardDescription></div></CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <Field label="Amount tolerance (₹)" hint="Absorbs invoice round-off"><Input inputMode="decimal" value={data.amount_tolerance} onChange={set("amount_tolerance")} /></Field>
        <Field label="Duplicate window (days)"><Input type="number" value={data.duplicate_window_days} onChange={set("duplicate_window_days")} /></Field>
        <Field label="PO unit-price tolerance (%)"><Input inputMode="decimal" value={data.po_price_tolerance_pct} onChange={set("po_price_tolerance_pct")} /></Field>
        <Field label="PO quantity tolerance (%)"><Input inputMode="decimal" value={data.po_qty_tolerance_pct} onChange={set("po_qty_tolerance_pct")} /></Field>
        <div className="sm:col-span-2 flex justify-end"><Button loading={busy} onClick={async () => {
          setBusy(true);
          try { setData(await api<Settings>("/company/settings", { method: "PUT", body: json({ ...data, duplicate_window_days: Number(data.duplicate_window_days) }) })); toast.success("Tolerances saved — re-run checks on open invoices to apply"); }
          catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
        }}>Save tolerances</Button></div>
      </CardContent>
    </Card>
  );
}

function SecurityCard() {
  const { data, setData } = useFetch<Settings>("/company/settings");
  const [busy, setBusy] = useState(false);
  if (!data) return <Skeleton className="h-48" />;
  const save = async (patch: Partial<Settings>) => {
    setBusy(true);
    try { setData(await api<Settings>("/company/settings", { method: "PUT", body: json({ ...data, ...patch, duplicate_window_days: Number(data.duplicate_window_days) }) })); toast.success("Security settings saved"); }
    catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Card>
      <CardHeader><div><CardTitle>Security & notifications</CardTitle><CardDescription>Company-wide policies.</CardDescription></div></CardHeader>
      <CardContent className="space-y-4 text-sm">
        <label className="flex items-start gap-3">
          <input type="checkbox" className="mt-1" checked={data.require_mfa} disabled={busy} onChange={(e) => save({ require_mfa: e.target.checked })} />
          <span><span className="font-medium">Require two-factor authentication for everyone</span><br />
            <span className="text-muted-foreground">Users without 2FA are signed out and must set it up at their next sign-in. Turn on 2FA for your own account first.</span></span>
        </label>
        <label className="flex items-start gap-3">
          <input type="checkbox" className="mt-1" checked={data.notify_approvers} disabled={busy} onChange={(e) => save({ notify_approvers: e.target.checked })} />
          <span><span className="font-medium">Email approvers when an invoice is waiting for them</span><br />
            <span className="text-muted-foreground">Submitters are always told when their invoice is approved or rejected.</span></span>
        </label>
      </CardContent>
    </Card>
  );
}

function PolicyCard() {
  const { data } = useFetch<Policy>("/company/approval-policy");
  const [p, setP] = useState<Policy | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setP(data); }, [data]);
  if (!p) return <Skeleton className="h-72" />;
  const setLevel = (i: number, patch: Partial<Level>) => setP({ ...p, levels: p.levels.map((l, j) => (j === i ? { ...l, ...patch } : l)) });
  return (
    <Card className="xl:col-span-2">
      <CardHeader><div><CardTitle>Approval policy</CardTitle><CardDescription>A level applies when the invoice grand total is at least its threshold. Level 1 should start at ₹0.</CardDescription></div></CardHeader>
      <CardContent className="space-y-4">
        {p.levels.map((l, i) => (
          <div key={i} className="grid items-end gap-3 rounded-lg border p-3 sm:grid-cols-[60px_1fr_160px_180px_40px]">
            <Field label="Level"><Input type="number" min={1} max={5} value={l.level} onChange={(e) => setLevel(i, { level: Number(e.target.value) })} /></Field>
            <Field label="Name"><Input value={l.name} onChange={(e) => setLevel(i, { name: e.target.value })} /></Field>
            <Field label="Role"><Select value={l.role} onChange={(e) => setLevel(i, { role: e.target.value as Level["role"] })}><option value="approver">Approver</option><option value="admin">Admin</option></Select></Field>
            <Field label="Applies from (₹)"><Input inputMode="decimal" value={l.min_amount} onChange={(e) => setLevel(i, { min_amount: e.target.value })} /></Field>
            <Button variant="ghost" size="icon" disabled={p.levels.length === 1} onClick={() => setP({ ...p, levels: p.levels.filter((_, j) => j !== i) })} aria-label="Remove level"><Trash2 /></Button>
          </div>
        ))}
        {p.levels.length < 5 && <Button variant="outline" size="sm" onClick={() => setP({ ...p, levels: [...p.levels, { level: p.levels.length + 1, name: "Additional approval", role: "approver", min_amount: "100000" }] })}><Plus /> Add level</Button>}
        <div className="space-y-2 border-t pt-4 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={p.allow_self_approval} onChange={(e) => setP({ ...p, allow_self_approval: e.target.checked })} /> Allow users to approve invoices they submitted <span className="text-xs text-warning">(weakens segregation of duties)</span></label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={p.allow_critical_override} onChange={(e) => setP({ ...p, allow_critical_override: e.target.checked })} /> Allow admins to override critical validation errors with a written justification</label>
        </div>
        <div className="flex justify-end"><Button loading={busy} onClick={async () => {
          setBusy(true);
          try { setP(await api<Policy>("/company/approval-policy", { method: "PUT", body: json(p) })); toast.success("Approval policy saved — applies to new submissions"); }
          catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
        }}>Save policy</Button></div>
      </CardContent>
    </Card>
  );
}

function SystemCard() {
  const { data } = useFetch<SystemStatus>("/system/status");
  if (!data) return <Skeleton className="h-72" />;
  const row = (k: string, v: React.ReactNode) => <div className="flex justify-between gap-4 border-b py-2 last:border-0 text-sm"><span className="text-muted-foreground">{k}</span><span className="text-right">{v}</span></div>;
  return (
    <Card>
      <CardHeader><div><CardTitle>System status</CardTitle><CardDescription>Read-only. Configured through server environment variables.</CardDescription></div></CardHeader>
      <CardContent>
        {row("Environment", data.environment)}
        {row("Database", data.database)}
        {row("Document storage", data.storage)}
        {row("OCR", `${data.ocr.engine} · ${data.ocr.available ? "available" : "not available"}`)}
        {row("AI provider", `${data.ai.provider}${data.ai.model ? ` (${data.ai.model})` : ""}`)}
        {row("Virus scanning", data.malware_scanning.engine === "clamav"
          ? `ClamAV · ${data.malware_scanning.available ? data.malware_scanning.version ?? "available" : "NOT reachable"}${data.malware_scanning.fail_closed ? " · fail-closed" : ""}`
          : "PDF active-content policy only (ClamAV off)")}
        {row("Email", `${data.email.provider} · ${data.email.from}`)}
        {row("Upload limits", `${data.limits.max_upload_mb} MB · ${data.limits.max_pdf_pages} pages`)}
        <Callout tone={data.ai.available ? "info" : "warning"} className="mt-3">{data.ai.detail}</Callout>
        {!data.ocr.available && <Callout tone="warning" className="mt-2">Tesseract is not available: scanned PDFs and images cannot be read. Digital PDFs still work.</Callout>}
      </CardContent>
    </Card>
  );
}
