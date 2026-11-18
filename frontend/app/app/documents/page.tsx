"use client";

import { Download, FolderOpen, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { RequirePermission } from "@/components/app/guard";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Select } from "@/components/ui/input";
import { PageHeader, Pagination } from "@/components/ui/page";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api, download, errorMessage } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { DocumentInfo, Page } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { bytes, dateTime } from "@/lib/utils";

export default function DocumentsPage() {
  const { can } = useSession();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, reload } = useFetch<Page<DocumentInfo>>("/documents", { status, page, page_size: 20 });
  const [del, setDel] = useState<DocumentInfo | null>(null);
  return (
    <RequirePermission perm="documents:read">
      <PageHeader title="Documents" description="Original files are stored privately and served only through authorised downloads." />
      <Card>
        <div className="border-b p-3">
          <Select className="w-48" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Status">
            <option value="">All documents</option><option value="processed">Processed</option><option value="failed">Failed</option><option value="uploaded">Not processed</option>
          </Select>
        </div>
        {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>
          : data.items.length === 0 ? <EmptyState icon={FolderOpen} title="No documents" />
          : (<>
            <Table>
              <THead><tr><TH>File</TH><TH>Type</TH><TH>Size</TH><TH>Pages</TH><TH>Status</TH><TH>Scan</TH><TH>Uploaded</TH><TH>Invoice</TH><TH>SHA-256</TH><TH /></tr></THead>
              <TBody>
                {data.items.map((d) => (
                  <TR key={d.id}>
                    <TD className="max-w-56 truncate font-medium">{d.original_filename}{d.is_demo && <span className="ml-2 text-[10px] uppercase text-muted-foreground">demo</span>}</TD>
                    <TD className="text-xs text-muted-foreground">{d.content_type.split("/")[1].toUpperCase()}</TD>
                    <TD className="num text-muted-foreground">{bytes(d.size_bytes)}</TD>
                    <TD className="num text-muted-foreground">{d.page_count ?? "—"}</TD>
                    <TD><StatusBadge value={d.status} />{d.error_message && <p className="mt-0.5 max-w-48 truncate text-xs text-danger" title={d.error_message}>{d.error_message}</p>}</TD>
                    <TD className="text-xs">{d.scan_result === "clean" ? <span className="text-success" title={d.scan_engine ?? ""}>Clean · {d.scan_engine}</span>
                      : <span className="text-muted-foreground" title="No virus scanner was configured for this upload">{d.scan_result === "not_scanned" ? "Not scanned" : "—"}</span>}</TD>
                    <TD className="num whitespace-nowrap text-xs text-muted-foreground">{dateTime(d.created_at)}</TD>
                    <TD>{d.invoice_id ? <Link className="text-primary hover:underline" href={`/app/invoices/${d.invoice_id}`}>Open</Link> : "—"}</TD>
                    <TD className="font-mono text-[11px] text-muted-foreground" title={d.sha256}>{d.sha256.slice(0, 12)}…</TD>
                    <TD className="whitespace-nowrap text-right">
                      <Button size="icon" variant="ghost" aria-label="Download" onClick={() => download(`/documents/${d.id}/download`, { inline: false }).catch((e) => toast.error(errorMessage(e)))}><Download /></Button>
                      {can("documents:delete") && <Button size="icon" variant="ghost" aria-label="Delete" onClick={() => setDel(d)}><Trash2 /></Button>}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination page={page} pageSize={20} total={data.total} onPage={setPage} />
          </>)}
      </Card>
      <ConfirmDialog open={!!del} onOpenChange={(o) => !o && setDel(null)} title={`Delete ${del?.original_filename}?`} confirmLabel="Delete permanently"
        description="The stored file is removed. Documents of pending or approved invoices are retained for audit and cannot be deleted."
        onConfirm={async () => { try { await api(`/documents/${del!.id}`, { method: "DELETE" }); toast.success("Document deleted"); void reload(); } catch (e) { toast.error(errorMessage(e)); } }} />
    </RequirePermission>
  );
}
