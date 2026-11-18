"use client";

import { Download, FileText, Plus, Search, Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { RequirePermission } from "@/components/app/guard";
import { InvoiceTable } from "@/components/app/invoice-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/input";
import { PageHeader, Pagination } from "@/components/ui/page";
import { download, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { InvoiceListItem, Page, Supplier } from "@/lib/types";
import { useDebounced } from "@/lib/use-debounce";
import { useFetch } from "@/lib/use-fetch";

const STATUSES = ["review_required", "extracted", "pending_approval", "approved", "rejected", "failed_processing", "draft", "archived"];
const LABEL: Record<string, string> = { review_required: "Needs review", extracted: "Ready to submit", pending_approval: "Pending approval", failed_processing: "Processing failed" };

export default function InvoicesPage() {
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [f, setF] = useState({ status: "", validation_status: "", duplicate_status: "", supplier_id: "", date_from: "", date_to: "", sort: "-created" });
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const query = { ...f, q: dq, page, page_size: 20, include_archived: f.status === "archived" };
  const { data, error, loading, reload } = useFetch<Page<InvoiceListItem>>("/invoices", query);
  const suppliers = useFetch<Page<Supplier>>("/suppliers", { page_size: 100 });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => { setF({ ...f, [k]: e.target.value }); setPage(1); };
  const [exporting, setExporting] = useState(false);

  const exportXlsx = async () => {
    setExporting(true);
    try { await download("/reports/invoices/export", { status: f.status, supplier_id: f.supplier_id, date_from: f.date_from, date_to: f.date_to }); }
    catch (e) { toast.error(errorMessage(e)); } finally { setExporting(false); }
  };

  return (
    <RequirePermission perm="invoices:read">
      <PageHeader title="Invoices" description="Search, filter and open any invoice for review."
        actions={<>
          {can("reports:export") && <Button variant="outline" onClick={exportXlsx} loading={exporting}><Download /> Export Excel</Button>}
          {can("invoices:write") && <Button variant="outline" asChild><Link href="/app/invoices/new"><Plus /> Manual entry</Link></Button>}
          {can("documents:upload") && <Button asChild><Link href="/app/invoices/upload"><Upload /> Upload</Link></Button>}
        </>} />
      <Card>
        <div className="grid gap-2 border-b p-3 sm:grid-cols-2 lg:grid-cols-[2fr_repeat(4,1fr)]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search number, supplier or PO…" className="pl-9" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Search invoices" />
          </div>
          <Select value={f.status} onChange={set("status")} aria-label="Status"><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{LABEL[s] ?? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())}</option>)}</Select>
          <Select value={f.validation_status} onChange={set("validation_status")} aria-label="Validation"><option value="">Any validation</option><option value="passed">Passed</option><option value="warnings">Warnings</option><option value="failed">Failed</option></Select>
          <Select value={f.duplicate_status} onChange={set("duplicate_status")} aria-label="Duplicates"><option value="">Any duplicate state</option><option value="duplicate">Duplicate</option><option value="possible_duplicate">Possible duplicate</option><option value="none">No duplicate</option></Select>
          <Select value={f.supplier_id} onChange={set("supplier_id")} aria-label="Supplier"><option value="">All suppliers</option>{suppliers.data?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
          <div className="flex items-center gap-2 lg:col-span-2">
            <Input type="date" value={f.date_from} onChange={set("date_from")} aria-label="From date" />
            <span className="text-xs text-muted-foreground">to</span>
            <Input type="date" value={f.date_to} onChange={set("date_to")} aria-label="To date" />
          </div>
          <Select value={f.sort} onChange={set("sort")} aria-label="Sort"><option value="-created">Newest first</option><option value="-date">Invoice date ↓</option><option value="date">Invoice date ↑</option><option value="-amount">Amount ↓</option><option value="amount">Amount ↑</option></Select>
        </div>
        {error ? <ErrorState message={error} onRetry={reload} /> : loading && !data ? <div className="space-y-2 p-4">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9" />)}</div>
          : data && data.items.length === 0 ? <EmptyState icon={FileText} title="No invoices match these filters" description="Try clearing filters, or upload a new invoice." />
          : data && <><div className={loading ? "opacity-60" : ""}><InvoiceTable items={data.items} /></div><Pagination page={page} pageSize={20} total={data.total} onPage={setPage} /></>}
      </Card>
    </RequirePermission>
  );
}
