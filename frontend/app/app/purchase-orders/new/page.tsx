"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { RequirePermission } from "@/components/app/guard";
import { POForm, poToValues } from "@/components/app/po-form";
import { PageHeader } from "@/components/ui/page";
import { api, errorMessage, json } from "@/lib/api";
import type { PurchaseOrder } from "@/lib/types";

export default function NewPOPage() {
  const router = useRouter();
  return (
    <RequirePermission perm="po:write">
      <PageHeader title="New purchase order" />
      <POForm initial={poToValues(null)} onSubmit={async (body) => {
        try { const po = await api<PurchaseOrder>("/purchase-orders", { method: "POST", body: json(body) }); toast.success("Purchase order created"); router.push(`/app/purchase-orders/${po.id}`); }
        catch (e) { toast.error(errorMessage(e)); }
      }} />
    </RequirePermission>
  );
}
