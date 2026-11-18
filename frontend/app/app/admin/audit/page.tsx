"use client";

import { ScrollText } from "lucide-react";
import Link from "next/link";
import { Fragment, useState } from "react";
import { RequirePermission } from "@/components/app/guard";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/input";
import { PageHeader, Pagination } from "@/components/ui/page";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { AuditLog, Page } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { dateTime, humanize } from "@/lib/utils";

const PREFIXES = ["auth", "invoice", "document", "supplier", "po", "user", "company", "settings", "approval_policy", "report"];

export default function AuditPage() {
  const [f, setF] = useState({ action: "", entity_type: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const { data, error, reload } = useFetch<Page<AuditLog>>("/audit-logs", { ...f, page, page_size: 50 });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => { setF({ ...f, [k]: e.target.value }); setPage(1); };
  return (
    <RequirePermission perm="audit:read">
      <PageHeader title="Audit log" description="Append-only record of security and business events. Entries cannot be edited or deleted through the application." />
      <Card>
        <div className="grid gap-2 border-b p-3 sm:grid-cols-4">
          <Select value={f.action} onChange={set("action")} aria-label="Action"><option value="">All actions</option>{PREFIXES.map((p) => <option key={p} value={p}>{humanize(p)}</option>)}</Select>
          <Select value={f.entity_type} onChange={set("entity_type")} aria-label="Entity"><option value="">All entities</option>{["invoice", "document", "supplier", "purchase_order", "user", "company"].map((p) => <option key={p} value={p}>{humanize(p)}</option>)}</Select>
          <Input type="date" value={f.date_from} onChange={set("date_from")} aria-label="From" />
          <Input type="date" value={f.date_to} onChange={set("date_to")} aria-label="To" />
        </div>
        {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <div className="p-4"><Skeleton className="h-60" /></div>
          : data.items.length === 0 ? <EmptyState icon={ScrollText} title="No audit entries for these filters" /> : (<>
            <Table>
              <THead><tr><TH>Time</TH><TH>Action</TH><TH>Actor</TH><TH>Entity</TH><TH>IP</TH><TH /></tr></THead>
              <TBody>
                {data.items.map((a) => (
                  <Fragment key={a.id}>
                    <TR>
                      <TD className="num whitespace-nowrap text-xs text-muted-foreground">{dateTime(a.created_at)}</TD>
                      <TD className="font-medium">{a.action}</TD>
                      <TD className="text-muted-foreground">{a.actor_email ?? "system"}</TD>
                      <TD className="text-xs">{a.entity_type === "invoice" && a.entity_id ? <Link className="text-primary hover:underline" href={`/app/invoices/${a.entity_id}`}>Invoice</Link> : humanize(a.entity_type)}</TD>
                      <TD className="font-mono text-xs text-muted-foreground">{a.ip_address ?? "—"}</TD>
                      <TD>{a.meta && <button className="text-xs text-primary hover:underline" onClick={() => setOpen(open === a.id ? null : a.id)}>{open === a.id ? "Hide" : "Details"}</button>}</TD>
                    </TR>
                    {open === a.id && <tr><td colSpan={6} className="bg-surface-muted/50 px-4 py-3"><pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(a.meta, null, 2)}</pre></td></tr>}
                  </Fragment>
                ))}
              </TBody>
            </Table>
            <Pagination page={page} pageSize={50} total={data.total} onPage={setPage} />
          </>)}
      </Card>
    </RequirePermission>
  );
}
