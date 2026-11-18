"use client";

import { Plus, Search, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { RequirePermission } from "@/components/app/guard";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/input";
import { PageHeader, Pagination } from "@/components/ui/page";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useSession } from "@/lib/session";
import type { Page, PurchaseOrder } from "@/lib/types";
import { useDebounced } from "@/lib/use-debounce";
import { useFetch } from "@/lib/use-fetch";
import { date, money } from "@/lib/utils";

export default function PurchaseOrdersPage() {
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const { data, error, reload } = useFetch<Page<PurchaseOrder>>("/purchase-orders", { q: dq, status, page, page_size: 20 });
  return (
    <RequirePermission perm="po:read">
      <PageHeader title="Purchase orders" description="Invoices referencing a PO number are matched line by line automatically."
        actions={can("po:write") && <Button asChild><Link href="/app/purchase-orders/new"><Plus /> New purchase order</Link></Button>} />
      <Card>
        <div className="flex flex-wrap gap-2 border-b p-3">
          <div className="relative min-w-60 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search PO number or supplier…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Search purchase orders" />
          </div>
          <Select className="w-48" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Status">
            <option value="">All statuses</option><option value="open">Open</option><option value="partially_invoiced">Partially invoiced</option><option value="closed">Closed</option><option value="cancelled">Cancelled</option><option value="draft">Draft</option>
          </Select>
        </div>
        {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>
          : data.items.length === 0 ? <EmptyState icon={ShoppingCart} title="No purchase orders" />
          : (<>
            <Table>
              <THead><tr><TH>PO number</TH><TH>Supplier</TH><TH>PO date</TH><TH>Delivery</TH><TH className="text-right">Total</TH><TH>Status</TH></tr></THead>
              <TBody>
                {data.items.map((p) => (
                  <TR key={p.id}>
                    <TD><Link href={`/app/purchase-orders/${p.id}`} className="font-medium text-primary hover:underline">{p.po_number}</Link></TD>
                    <TD>{p.supplier.name}</TD>
                    <TD className="num text-muted-foreground">{date(p.po_date)}</TD>
                    <TD className="num text-muted-foreground">{date(p.expected_delivery_date)}</TD>
                    <TD className="num text-right font-medium">{money(p.total_amount)}</TD>
                    <TD><StatusBadge value={p.status} /></TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination page={page} pageSize={20} total={data.total} onPage={setPage} />
          </>)}
      </Card>
    </RequirePermission>
  );
}
