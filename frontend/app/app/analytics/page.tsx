"use client";

import { RequirePermission } from "@/components/app/guard";
import { ApprovalTrendChart, HorizontalBars, MonthlyValueChart } from "@/components/app/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/feedback";
import { PageHeader, Stat } from "@/components/ui/page";
import type { ApprovalTrends, InvoiceTrends, Overview, SupplierStats } from "@/lib/analytics-types";
import { useFetch } from "@/lib/use-fetch";
import { humanize, money } from "@/lib/utils";

export default function AnalyticsPage() {
  const ov = useFetch<Overview>("/analytics/overview");
  const tr = useFetch<InvoiceTrends>("/analytics/invoices");
  const ap = useFetch<ApprovalTrends>("/analytics/approvals", { months: 12 });
  const sp = useFetch<SupplierStats>("/analytics/suppliers");
  const box = (title: string, body: React.ReactNode, desc?: string) => (
    <Card><CardHeader><div><CardTitle>{title}</CardTitle>{desc && <CardDescription>{desc}</CardDescription>}</div></CardHeader><CardContent>{body ?? <Skeleton className="h-60" />}</CardContent></Card>
  );
  return (
    <RequirePermission perm="analytics:read">
      <PageHeader title="Analytics" description="All figures are computed live from your company's invoices (archived invoices excluded)." />
      {ov.data && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Invoice value" value={money(ov.data.total_value, true)} sub={`${ov.data.total_invoices} invoices`} />
          <Stat label="Approved value" value={money(ov.data.approved_amount, true)} tone="success" />
          <Stat label="Pending value" value={money(ov.data.pending_amount, true)} />
          <Stat label="Avg. time to decision" value={ap.data?.average_hours_to_decision != null ? `${ap.data.average_hours_to_decision} h` : "—"} />
        </div>
      )}
      <div className="grid gap-6 xl:grid-cols-2">
        {box("Monthly invoice value", tr.data && <MonthlyValueChart data={tr.data.monthly} />, "Total vs approved, by invoice date")}
        {box("Monthly approval trends", ap.data && <ApprovalTrendChart data={ap.data.monthly} />)}
        {box("Supplier-wise invoice totals", sp.data && <HorizontalBars isMoney valueLabel="Total" data={sp.data.suppliers.map((s) => ({ name: s.name, value: Number(s.total) }))} />)}
        {box("Invoice status distribution", ov.data && <HorizontalBars valueLabel="Invoices" data={ov.data.status_distribution.map((s) => ({ name: humanize(s.status), value: s.count }))} />)}
        {box("Validation issue distribution", tr.data && (tr.data.validation_issues.length ? <HorizontalBars valueLabel="Invoices" data={tr.data.validation_issues.map((v) => ({ name: v.issue, value: v.count }))} /> : <p className="py-10 text-center text-sm text-muted-foreground">No open validation issues.</p>), "Failed checks on the latest validation of each invoice")}
      </div>
    </RequirePermission>
  );
}
