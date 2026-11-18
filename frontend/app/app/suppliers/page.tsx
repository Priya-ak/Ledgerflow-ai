"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Archive, Pencil, Plus, Search, Truck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { RequirePermission } from "@/components/app/guard";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { PageHeader, Pagination } from "@/components/ui/page";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api, errorMessage, json } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Page, Supplier } from "@/lib/types";
import { useDebounced } from "@/lib/use-debounce";
import { useFetch } from "@/lib/use-fetch";

const schema = z.object({
  name: z.string().trim().min(2, "Required"),
  code: z.string().trim().min(1, "Required").regex(/^[A-Za-z0-9_-]+$/, "Letters, digits, - and _ only"),
  gstin: z.string().trim().toUpperCase().regex(/^$|^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/, "Invalid GSTIN format"),
  email: z.string().trim().email("Invalid email").or(z.literal("")),
  phone: z.string().max(40), contact_person: z.string().max(200), address: z.string().max(1000),
  payment_terms_days: z.coerce.number().int().min(0).max(365),
  status: z.enum(["active", "inactive", "archived"]),
});
type Values = z.infer<typeof schema>;
const blank: Values = { name: "", code: "", gstin: "", email: "", phone: "", contact_person: "", address: "", payment_terms_days: 30, status: "active" };

export default function SuppliersPage() {
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  const { data, error, reload } = useFetch<Page<Supplier>>("/suppliers", { q: dq, status, page, page_size: 20 });
  const [editing, setEditing] = useState<Supplier | "new" | null>(null);
  const [archiving, setArchiving] = useState<Supplier | null>(null);

  return (
    <RequirePermission perm="suppliers:read">
      <PageHeader title="Suppliers" description="Master data used for invoice matching and GSTIN consistency checks."
        actions={can("suppliers:write") && <Button onClick={() => setEditing("new")}><Plus /> New supplier</Button>} />
      <Card>
        <div className="flex flex-wrap gap-2 border-b p-3">
          <div className="relative min-w-60 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search name, code or GSTIN…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Search suppliers" />
          </div>
          <Select className="w-44" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Status"><option value="">Active & inactive</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="archived">Archived</option></Select>
        </div>
        {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>
          : data.items.length === 0 ? <EmptyState icon={Truck} title="No suppliers found" action={can("suppliers:write") && <Button onClick={() => setEditing("new")}><Plus /> Add supplier</Button>} />
          : (<>
            <Table>
              <THead><tr><TH>Code</TH><TH>Name</TH><TH>GSTIN</TH><TH>Contact</TH><TH>Terms</TH><TH>Status</TH><TH /></tr></THead>
              <TBody>
                {data.items.map((s) => (
                  <TR key={s.id}>
                    <TD className="font-mono text-xs">{s.code}</TD>
                    <TD className="font-medium">{s.name}</TD>
                    <TD className="font-mono text-xs">{s.gstin ?? "—"}</TD>
                    <TD className="text-muted-foreground">{s.contact_person ?? "—"}<br /><span className="text-xs">{s.email}</span></TD>
                    <TD className="num">{s.payment_terms_days} days</TD>
                    <TD><StatusBadge value={s.status} /></TD>
                    <TD className="text-right">
                      {can("suppliers:write") && <Button size="icon" variant="ghost" onClick={() => setEditing(s)} aria-label={`Edit ${s.name}`}><Pencil /></Button>}
                      {can("suppliers:delete") && s.status !== "archived" && <Button size="icon" variant="ghost" onClick={() => setArchiving(s)} aria-label={`Archive ${s.name}`}><Archive /></Button>}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <Pagination page={page} pageSize={20} total={data.total} onPage={setPage} />
          </>)}
      </Card>
      {editing && <SupplierDialog supplier={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void reload(); }} />}
      <ConfirmDialog open={!!archiving} onOpenChange={(o) => !o && setArchiving(null)} title={`Archive ${archiving?.name}?`} confirmLabel="Archive"
        description="Archived suppliers are hidden from matching and lists. Existing invoices and purchase orders keep their link."
        onConfirm={async () => { try { await api(`/suppliers/${archiving!.id}`, { method: "DELETE" }); toast.success("Supplier archived"); void reload(); } catch (e) { toast.error(errorMessage(e)); } }} />
    </RequirePermission>
  );
}

function SupplierDialog({ supplier, onClose, onSaved }: { supplier: Supplier | null; onClose: () => void; onSaved: () => void }) {
  const init: Values = supplier ? {
    name: supplier.name, code: supplier.code, gstin: supplier.gstin ?? "", email: supplier.email ?? "", phone: supplier.phone ?? "",
    contact_person: supplier.contact_person ?? "", address: supplier.address ?? "", payment_terms_days: supplier.payment_terms_days, status: supplier.status as Values["status"],
  } : blank;
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: init });
  const submit = async (v: Values) => {
    const body = { ...v, gstin: v.gstin || null, email: v.email || null, phone: v.phone || null, contact_person: v.contact_person || null, address: v.address || null };
    try {
      await api(supplier ? `/suppliers/${supplier.id}` : "/suppliers", { method: supplier ? "PUT" : "POST", body: json(body) });
      toast.success(supplier ? "Supplier updated" : "Supplier created");
      onSaved();
    } catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={supplier ? `Edit ${supplier.name}` : "New supplier"} wide>
        <form onSubmit={handleSubmit(submit)} className="grid gap-4 sm:grid-cols-2" noValidate>
          <Field label="Name" error={errors.name?.message}><Input {...register("name")} /></Field>
          <Field label="Supplier code" error={errors.code?.message}><Input {...register("code")} /></Field>
          <Field label="GSTIN" error={errors.gstin?.message} hint="Format and check digit are verified"><Input className="uppercase" maxLength={15} {...register("gstin")} /></Field>
          <Field label="Payment terms (days)" error={errors.payment_terms_days?.message}><Input type="number" {...register("payment_terms_days")} /></Field>
          <Field label="Contact person"><Input {...register("contact_person")} /></Field>
          <Field label="Email" error={errors.email?.message}><Input type="email" {...register("email")} /></Field>
          <Field label="Phone"><Input {...register("phone")} /></Field>
          <Field label="Status"><Select {...register("status")}><option value="active">Active</option><option value="inactive">Inactive</option><option value="archived">Archived</option></Select></Field>
          <Field label="Address" className="sm:col-span-2"><Textarea rows={2} {...register("address")} /></Field>
          <div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" loading={isSubmitting}>Save supplier</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
