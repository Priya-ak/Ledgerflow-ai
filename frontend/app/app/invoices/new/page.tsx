"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { RequirePermission } from "@/components/app/guard";
import { InvoiceForm, toFormValues, toPayload } from "@/components/app/invoice-form";
import { PageHeader } from "@/components/ui/page";
import { api, errorMessage, json } from "@/lib/api";
import type { InvoiceDetail } from "@/lib/types";

export default function NewInvoicePage() {
  const router = useRouter();
  return (
    <RequirePermission perm="invoices:write">
      <PageHeader title="Manual invoice entry" description="For invoices without a document. The same validation, duplicate and PO checks run on save." />
      <InvoiceForm formId="new-invoice" initial={toFormValues(null)} submitLabel="Create invoice" onSubmit={async (v) => {
        try {
          const inv = await api<InvoiceDetail>("/invoices", { method: "POST", body: json(toPayload(v)) });
          toast.success("Invoice created");
          router.push(`/app/invoices/${inv.id}`);
        } catch (e) { toast.error(errorMessage(e)); }
      }} />
    </RequirePermission>
  );
}
