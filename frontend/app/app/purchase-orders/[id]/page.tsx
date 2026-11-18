"use client";

import { ArrowLeft, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { RequirePermission } from "@/components/app/guard";
import { POForm, poToValues } from "@/components/app/po-form";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { api, errorMessage, json } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { PurchaseOrder } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { money } from "@/lib/utils";

export default function POPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { can } = useSession();
  const { data, error, reload, setData } = useFetch<PurchaseOrder>(`/purchase-orders/${id}`);
  const [confirm, setConfirm] = useState(false);
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <Skeleton className="h-96" />;
  const locked = ["closed", "cancelled"].includes(data.status) || !can("po:write");
  return (
    <RequirePermission perm="po:read">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/app/purchase-orders" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"><ArrowLeft className="size-3.5" /> Purchase orders</Link>
          <h1 className="mt-1 text-xl font-semibold">{data.po_number} <span className="font-normal text-muted-foreground">· {data.supplier.name}</span></h1>
          <div className="mt-2 flex items-center gap-2"><StatusBadge value={data.status} /><span className="num text-sm font-semibold">{money(data.total_amount)}</span></div>
        </div>
        {can("po:delete") && data.status !== "cancelled" && <Button variant="outline" onClick={() => setConfirm(true)}><Trash2 /> Delete / cancel</Button>}
      </div>
      <POForm initial={poToValues(data)} readOnly={locked} onSubmit={async (body) => {
        try { setData(await api<PurchaseOrder>(`/purchase-orders/${id}`, { method: "PUT", body: json(body) })); toast.success("Purchase order saved"); }
        catch (e) { toast.error(errorMessage(e)); }
      }} />
      <ConfirmDialog open={confirm} onOpenChange={setConfirm} title="Delete this purchase order?" confirmLabel="Continue"
        description="If any invoice references this PO it will be cancelled instead of deleted, preserving the matching history."
        onConfirm={async () => {
          try { const r = await api<PurchaseOrder>(`/purchase-orders/${id}`, { method: "DELETE" }); toast.success(r.status === "cancelled" ? "Purchase order cancelled" : "Purchase order deleted"); router.push("/app/purchase-orders"); }
          catch (e) { toast.error(errorMessage(e)); }
        }} />
    </RequirePermission>
  );
}
