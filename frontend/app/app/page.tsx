"use client";

import { ArrowRight, Inbox, Upload } from "lucide-react";
import Link from "next/link";
import { ApprovalTrendChart, HorizontalBars, MonthlyValueChart } from "@/components/app/charts";
import { InvoiceTable } from "@/components/app/invoice-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { PageHeader, Stat } from "@/components/ui/page";
import { StatusBadge } from "@/components/ui/badge";
import type { ApprovalTrends, InvoiceTrends, Overview, SupplierStats } from "@/lib/analytics-types";
import { useSession } from "@/lib/session";
import type { ApprovalListItem, AuditLog, InvoiceListItem, Page } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { dateTime, humanize, money } from "@/lib/utils";

export default function Dashboard() {
  const { me } = useSession();
  if (!me) return <Skeleton className="h-64" />;
  const role = me.user.role;
  return (
    <>
      <PageHeader title={`Good ${greeting()}, ${me.user.full_name.split(" ")[0]}`}
        description={role === "admin" ? "Company overview and controls." : role === "accountant" ? "Your processing queue and exceptions." : "Invoices waiting for your decision."}
        actions={role !== "approver" ? <Button asChild><Link href="/app/invoices/upload"><Upload /> Upload invoices</Link></Button> : <Button asChild><Link href="/app/approvals"><Inbox /> Open approval queue</Link></Button>} />
      {role === "admin" && <AdminDashboard />}
      {role === "accountant" && <AccountantDashboard />}
      {role === "approver" && <ApproverDashboard />}
    </>
  );
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening";
}

function useOverview() {
  return useFetch<Overview>("/analytics/overview");
}

function StatsSkeleton() {
  return <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div>;
}

function AdminDashboard() {
  const ov = useOverview();
  const tr = useFetch<InvoiceTrends>("/analytics/invoices");
  const ap = useFetch<ApprovalTrends>("/analytics/approvals");
  const sp = useFetch<SupplierStats>("/analytics/suppliers");
  const act = useFetch<Page<AuditLog>>("/audit-logs", { page_size: 8 });
  if (ov.error) return <ErrorState message={ov.error} onRetry={ov.reload} />;
  const o = ov.data;
  return (
    <div className="space-y-6">
      {!o ? <StatsSkeleton /> : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Total invoices" value={o.total_invoices} sub={money(o.total_value)} />
          <Stat label="Pending approval" value={o.pending_count} sub={money(o.pending_amount)} />
          <Stat label="Approved" value={o.approved_count} sub={money(o.approved_amount)} tone="success" />
          <Stat label="Rejected" value={o.rejected_count} sub={money(o.rejected_amount)} />
          <Stat label="Validation exceptions" value={o.validation_exception_count} tone={o.validation_exception_count ? "danger" : "default"} />
          <Stat label="Duplicate warnings" value={o.duplicate_count} tone={o.duplicate_count ? "warning" : "default"} />
          <Stat label="Needs review" value={o.review_required_count} tone={o.review_required_count ? "warning" : "default"} />
          <Stat label="Active suppliers" value={o.active_suppliers} sub={`${o.open_purchase_orders} open POs`} />
        </div>
      )}
      <div className="grid gap-6 xl:grid-cols-2">
        <ChartCard title="Monthly invoice value" description="By invoice date, last 12 months">{tr.data ? <MonthlyValueChart data={tr.data.monthly} /> : <Skeleton className="h-60" />}</ChartCard>
        <ChartCard title="Approval decisions" description={ap.data?.average_hours_to_decision != null ? `Average ${ap.data.average_hours_to_decision} h from submission to decision` : "Last 6 months"}>{ap.data ? <ApprovalTrendChart data={ap.data.monthly} /> : <Skeleton className="h-60" />}</ChartCard>
        <ChartCard title="Top suppliers by value">{sp.data ? (sp.data.suppliers.length ? <HorizontalBars isMoney valueLabel="Total" data={sp.data.suppliers.map((s) => ({ name: s.name, value: Number(s.total) }))} /> : <Empty />) : <Skeleton className="h-60" />}</ChartCard>
        <ChartCard title="Invoice status distribution">{o ? <HorizontalBars valueLabel="Invoices" data={o.status_distribution.map((s) => ({ name: humanize(s.status), value: s.count }))} /> : <Skeleton className="h-60" />}</ChartCard>
      </div>
      <Card>
        <CardHeader><div><CardTitle>Recent activity</CardTitle><CardDescription>From the audit log</CardDescription></div>
          <Button variant="ghost" size="sm" asChild><Link href="/app/admin/audit">View all <ArrowRight /></Link></Button></CardHeader>
        {act.data ? (
          <ul className="divide-y">
            {act.data.items.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-4 px-5 py-2.5 text-sm">
                <span><span className="font-medium">{humanize(a.action)}</span> <span className="text-muted-foreground">by {a.actor_email ?? "system"}</span></span>
                <span className="num shrink-0 text-xs text-muted-foreground">{dateTime(a.created_at)}</span>
              </li>
            ))}
          </ul>
        ) : <CardContent><Skeleton className="h-32" /></CardContent>}
      </Card>
    </div>
  );
}

function AccountantDashboard() {
  const ov = useOverview();
  const review = useFetch<Page<InvoiceListItem>>("/invoices", { status: "review_required,failed_processing,rejected", page_size: 8 });
  const ready = useFetch<Page<InvoiceListItem>>("/invoices", { status: "extracted", page_size: 5 });
  const recent = useFetch<Page<InvoiceListItem>>("/invoices", { page_size: 6, sort: "-created" });
  const tr = useFetch<InvoiceTrends>("/analytics/invoices");
  const o = ov.data;
  return (
    <div className="space-y-6">
      {!o ? <StatsSkeleton /> : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Needs review" value={o.review_required_count} tone={o.review_required_count ? "warning" : "default"} />
          <Stat label="Ready to submit" value={o.ready_to_submit_count} />
          <Stat label="Validation exceptions" value={o.validation_exception_count} tone={o.validation_exception_count ? "danger" : "default"} />
          <Stat label="Duplicate warnings" value={o.duplicate_count} tone={o.duplicate_count ? "warning" : "default"} />
          <Stat label="Pending approval" value={o.pending_count} sub={money(o.pending_amount)} />
          <Stat label="Processing failures" value={o.failed_processing_count} tone={o.failed_processing_count ? "danger" : "default"} />
          <Stat label="Approved" value={o.approved_count} sub={money(o.approved_amount)} tone="success" />
          <Stat label="Open purchase orders" value={o.open_purchase_orders} />
        </div>
      )}
      <ListCard title="Requires your attention" description="Corrections, failed processing and rejected invoices" data={review} emptyText="Nothing needs correction right now." />
      <div className="grid gap-6 xl:grid-cols-2">
        <ListCard title="Ready to submit" description="Validated with no open review items" data={ready} emptyText="No invoices waiting for submission." compact />
        <ListCard title="Recently processed" data={recent} emptyText="Upload your first invoice to get started." compact />
      </div>
      <ChartCard title="Monthly invoice value">{tr.data ? <MonthlyValueChart data={tr.data.monthly} /> : <Skeleton className="h-60" />}</ChartCard>
      {tr.data && tr.data.validation_issues.length > 0 && (
        <ChartCard title="Most common validation issues"><HorizontalBars valueLabel="Invoices" data={tr.data.validation_issues.map((v) => ({ name: v.issue, value: v.count }))} /></ChartCard>
      )}
    </div>
  );
}

function ApproverDashboard() {
  const ov = useOverview();
  const ap = useFetch<ApprovalTrends>("/analytics/approvals");
  const queue = useFetch<Page<ApprovalListItem>>("/approvals", { actionable: true, page_size: 10 });
  const o = ov.data;
  return (
    <div className="space-y-6">
      {!o || !ap.data ? <StatsSkeleton /> : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Awaiting your decision" value={queue.data?.total ?? "…"} tone="warning" />
          <Stat label="Pending (company)" value={o.pending_count} sub={money(o.pending_amount)} />
          <Stat label="You approved" value={ap.data.my_decisions.approved ?? 0} tone="success" />
          <Stat label="You rejected" value={ap.data.my_decisions.rejected ?? 0} />
        </div>
      )}
      <Card>
        <CardHeader><div><CardTitle>Your approval queue</CardTitle><CardDescription>Invoices at a level you can decide</CardDescription></div>
          <Button variant="ghost" size="sm" asChild><Link href="/app/approvals">Open queue <ArrowRight /></Link></Button></CardHeader>
        {queue.data ? (queue.data.items.length ? <InvoiceTable compact items={queue.data.items.map((q) => q.invoice)} /> : <EmptyState icon={Inbox} title="You're all caught up" description="No invoices are waiting for your decision." />) : <CardContent><Skeleton className="h-32" /></CardContent>}
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <ChartCard title="Approval decisions" description={ap.data?.average_hours_to_decision != null ? `Average ${ap.data.average_hours_to_decision} h to decision` : undefined}>{ap.data ? <ApprovalTrendChart data={ap.data.monthly} /> : <Skeleton className="h-60" />}</ChartCard>
        <Card>
          <CardHeader><CardTitle>High-value pending invoices</CardTitle></CardHeader>
          {ap.data ? (ap.data.high_value_pending.length ? (
            <ul className="divide-y">{ap.data.high_value_pending.map((h) => (
              <li key={h.id} className="flex items-center justify-between px-5 py-3 text-sm">
                <Link className="text-primary hover:underline" href={`/app/invoices/${h.id}`}>{h.invoice_number ?? "Untitled"} <span className="text-muted-foreground">· {h.supplier}</span></Link>
                <span className="num font-medium">{money(h.grand_total)}</span>
              </li>))}</ul>
          ) : <Empty />) : <CardContent><Skeleton className="h-40" /></CardContent>}
        </Card>
      </div>
    </div>
  );
}

function ChartCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return <Card><CardHeader><div><CardTitle>{title}</CardTitle>{description && <CardDescription>{description}</CardDescription>}</div></CardHeader><CardContent>{children}</CardContent></Card>;
}

function Empty() {
  return <p className="py-10 text-center text-sm text-muted-foreground">No data yet.</p>;
}

function ListCard({ title, description, data, emptyText, compact }: { title: string; description?: string; data: ReturnType<typeof useFetch<Page<InvoiceListItem>>>; emptyText: string; compact?: boolean }) {
  return (
    <Card>
      <CardHeader><div><CardTitle>{title}</CardTitle>{description && <CardDescription>{description}</CardDescription>}</div>
        {data.data && data.data.total > data.data.items.length && <StatusBadge value={`${data.data.total} total`} />}</CardHeader>
      {data.error ? <ErrorState message={data.error} onRetry={data.reload} /> : data.data ? (data.data.items.length ? <InvoiceTable items={data.data.items} compact={compact} /> : <EmptyState icon={Inbox} title={emptyText} />) : <CardContent><Skeleton className="h-32" /></CardContent>}
    </Card>
  );
}
