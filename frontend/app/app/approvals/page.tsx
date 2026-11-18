"use client";

import { Inbox } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { RequirePermission } from "@/components/app/guard";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { PageHeader, Pagination } from "@/components/ui/page";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { ApprovalListItem, Page } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { cn, dateTime, money } from "@/lib/utils";

const VIEWS = [
  { key: "mine", label: "Awaiting me", query: { status: "pending", actionable: true } },
  { key: "pending", label: "All pending", query: { status: "pending" } },
  { key: "approved", label: "Approved", query: { status: "approved" } },
  { key: "rejected", label: "Rejected", query: { status: "rejected" } },
] as const;

export default function ApprovalsPage() {
  const [view, setView] = useState<(typeof VIEWS)[number]["key"]>("mine");
  const [page, setPage] = useState(1);
  const q = VIEWS.find((v) => v.key === view)!.query;
  const { data, error, loading, reload } = useFetch<Page<ApprovalListItem>>("/approvals", { ...q, page, page_size: 20 });
  return (
    <RequirePermission perm="approvals:read">
      <PageHeader title="Approvals" description="Open an invoice to compare the original document with extracted data before deciding." />
      <div className="mb-4 flex flex-wrap gap-1">
        {VIEWS.map((v) => (
          <Button key={v.key} size="sm" variant={view === v.key ? "default" : "outline"} onClick={() => { setView(v.key); setPage(1); }}>{v.label}</Button>
        ))}
      </div>
      <Card>
        {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <div className="space-y-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
          : data.items.length === 0 ? <EmptyState icon={Inbox} title={view === "mine" ? "Nothing is waiting for you" : "No approval requests"} />
          : (
            <div className={cn(loading && "opacity-60")}>
              <Table>
                <THead><tr><TH>Invoice</TH><TH>Supplier</TH><TH className="text-right">Amount</TH><TH>Validation</TH><TH>PO</TH><TH>Level</TH><TH>Submitted</TH><TH>Status</TH><TH /></tr></THead>
                <TBody>
                  {data.items.map((a) => {
                    const lv = a.required_levels.find((l) => l.level === a.current_level);
                    return (
                      <TR key={a.id}>
                        <TD><Link className="font-medium text-primary hover:underline" href={`/app/invoices/${a.invoice_id}`}>{a.invoice.invoice_number ?? "Untitled"}</Link></TD>
                        <TD className="max-w-48 truncate">{a.invoice.supplier?.name ?? a.invoice.supplier_name_raw}</TD>
                        <TD className="num text-right font-medium">{money(a.invoice.grand_total)}</TD>
                        <TD><StatusBadge value={a.invoice.validation_status} /></TD>
                        <TD><StatusBadge value={a.invoice.po_match_status} /></TD>
                        <TD className="text-xs">{a.status === "pending" ? `${a.current_level}/${a.required_levels.length} · ${lv?.name ?? ""}` : `${a.required_levels.length} level(s)`}</TD>
                        <TD className="num whitespace-nowrap text-xs text-muted-foreground">{dateTime(a.created_at)}</TD>
                        <TD><StatusBadge value={a.status} /></TD>
                        <TD>{a.can_decide && <Button size="sm" asChild><Link href={`/app/invoices/${a.invoice_id}`}>Review</Link></Button>}</TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
              <Pagination page={page} pageSize={20} total={data.total} onPage={setPage} />
            </div>
          )}
      </Card>
    </RequirePermission>
  );
}
