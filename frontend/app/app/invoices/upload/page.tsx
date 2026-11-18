"use client";

import { CheckCircle2, FileUp, Loader2, ScanText, XCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { RequirePermission } from "@/components/app/guard";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Callout } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/page";
import { api, errorMessage, json } from "@/lib/api";
import type { DocumentInfo, InvoiceDetail } from "@/lib/types";
import { bytes, cn, money } from "@/lib/utils";

const MAX_MB = 10;
const ACCEPT = ".pdf,.jpg,.jpeg,.png";

type Job = { id: string; file: File; stage: "queued" | "uploading" | "processing" | "done" | "error"; error?: string; invoice?: InvoiceDetail };

export default function UploadPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [drag, setDrag] = useState(false);
  const running = useRef(false);
  const input = useRef<HTMLInputElement>(null);

  const update = (id: string, patch: Partial<Job>) => setJobs((js) => js.map((j) => (j.id === id ? { ...j, ...patch } : j)));

  // Process strictly one document at a time: keeps memory low on 4 GB machines.
  const runQueue = useCallback(async (queue: Job[]) => {
    if (running.current) return;
    running.current = true;
    for (const job of queue) {
      try {
        update(job.id, { stage: "uploading" });
        const fd = new FormData();
        fd.append("file", job.file);
        const doc = await api<DocumentInfo>("/documents/upload", { method: "POST", body: fd });
        update(job.id, { stage: "processing" });
        const inv = await api<InvoiceDetail>("/invoices/extract", { method: "POST", body: json({ document_id: doc.id }) });
        update(job.id, { stage: "done", invoice: inv });
      } catch (e) {
        update(job.id, { stage: "error", error: errorMessage(e) });
      }
    }
    running.current = false;
  }, []);

  const add = (files: FileList | null) => {
    if (!files?.length) return;
    const fresh: Job[] = Array.from(files).slice(0, 20).map((file) => {
      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      const bad = !["pdf", "jpg", "jpeg", "png"].includes(ext) ? "Only PDF, JPG and PNG files are supported." : file.size > MAX_MB * 1024 * 1024 ? `File exceeds ${MAX_MB} MB.` : undefined;
      return { id: crypto.randomUUID(), file, stage: bad ? "error" : "queued", error: bad };
    });
    setJobs((js) => [...fresh, ...js]);
    void runQueue(fresh.filter((j) => j.stage === "queued"));
  };

  return (
    <RequirePermission perm="documents:upload">
      <PageHeader title="Upload invoices" description="PDF, JPG or PNG up to 10 MB. Files are processed one at a time: stored, read (PDF text or OCR), extracted, then checked." />
      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <div className="space-y-4">
          <div role="button" tabIndex={0} onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); add(e.dataTransfer.files); }}
            className={cn("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed bg-surface px-6 py-14 text-center transition-colors",
              drag ? "border-primary bg-primary-soft" : "hover:border-primary/50")}>
            <FileUp className="size-8 text-primary" />
            <p className="mt-3 text-sm font-medium">Drop invoice files here or click to browse</p>
            <p className="mt-1 text-xs text-muted-foreground">The file type is verified from its content, not its name.</p>
            <input ref={input} data-testid="file-input" type="file" accept={ACCEPT} multiple className="sr-only" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
          </div>
          {jobs.length > 0 && (
            <Card>
              <CardHeader><CardTitle>Processing queue</CardTitle></CardHeader>
              <ul className="divide-y">
                {jobs.map((j) => <JobRow key={j.id} job={j} />)}
              </ul>
            </Card>
          )}
        </div>
        <Card className="h-fit">
          <CardHeader><CardTitle>What happens to each file</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p className="flex gap-2"><ScanText className="size-4 shrink-0 text-primary" />Digital PDFs are read directly. Scans and photos are recognised with Tesseract OCR.</p>
            <p>Fields that cannot be read confidently are left empty and highlighted — LedgerFlow never fills in guesses.</p>
            <p>Validation, duplicate detection and purchase-order matching run automatically. You review everything before submitting for approval.</p>
            <Callout tone="info">Sample files live in <code className="text-xs">sample-data/synthetic-invoices/</code> in the repository.</Callout>
          </CardContent>
        </Card>
      </div>
    </RequirePermission>
  );
}

function JobRow({ job }: { job: Job }) {
  const inv = job.invoice;
  return (
    <li className="flex items-start gap-3 px-5 py-3" data-testid="upload-row">
      <div className="mt-0.5">
        {job.stage === "done" ? <CheckCircle2 className="size-4 text-success" /> : job.stage === "error" ? <XCircle className="size-4 text-danger" /> : <Loader2 className="size-4 animate-spin text-primary" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{job.file.name} <span className="font-normal text-muted-foreground">· {bytes(job.file.size)}</span></p>
        {job.stage === "error" && <p className="text-xs text-danger">{job.error}</p>}
        {job.stage === "uploading" && <p className="text-xs text-muted-foreground">Uploading and verifying…</p>}
        {job.stage === "processing" && <p className="text-xs text-muted-foreground">Reading text, extracting fields and running checks…</p>}
        {job.stage === "queued" && <p className="text-xs text-muted-foreground">Waiting…</p>}
        {inv && (
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
            <StatusBadge value={inv.status} /><StatusBadge value={inv.validation_status} />
            {inv.duplicate_status !== "none" && <StatusBadge value={inv.duplicate_status} />}
            <span className="num text-muted-foreground">{inv.invoice_number ?? "No invoice number"} · {money(inv.grand_total)}</span>
          </div>
        )}
      </div>
      {inv && <Button size="sm" variant="outline" asChild><Link href={`/app/invoices/${inv.id}`}>Review</Link></Button>}
    </li>
  );
}
