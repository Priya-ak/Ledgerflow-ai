"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import type { Page, PurchaseOrder, Supplier } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { money } from "@/lib/utils";

const num = (msg: string) => z.string().trim().regex(/^\d+(\.\d{1,3})?$/, msg);
const schema = z.object({
  supplier_id: z.string().min(1, "Select a supplier"),
  po_number: z.string().trim().min(1, "Required").max(60),
  po_date: z.string().min(1, "Required"),
  expected_delivery_date: z.string().optional(),
  status: z.enum(["draft", "open", "partially_invoiced", "closed", "cancelled"]),
  notes: z.string().max(2000).optional(),
  items: z.array(z.object({
    description: z.string().trim().min(1, "Required"), hsn_sac: z.string().regex(/^$|^\d{4,8}$/, "4–8 digits"),
    quantity: num("Qty > 0"), unit: z.string().max(20), unit_price: num("Price"), tax_rate: num("Rate"),
  })).min(1, "Add at least one line"),
});
export type POValues = z.infer<typeof schema>;

export function poToValues(po?: PurchaseOrder | null): POValues {
  return {
    supplier_id: po?.supplier_id ?? "", po_number: po?.po_number ?? "", po_date: po?.po_date ?? new Date().toISOString().slice(0, 10),
    expected_delivery_date: po?.expected_delivery_date ?? "", status: (po?.status as POValues["status"]) ?? "open", notes: po?.notes ?? "",
    items: po?.items?.map((i) => ({ description: i.description, hsn_sac: i.hsn_sac ?? "", quantity: i.quantity, unit: i.unit ?? "", unit_price: i.unit_price, tax_rate: i.tax_rate }))
      ?? [{ description: "", hsn_sac: "", quantity: "1", unit: "Nos", unit_price: "0", tax_rate: "18" }],
  };
}

export function POForm({ initial, onSubmit, readOnly }: { initial: POValues; onSubmit: (body: unknown) => Promise<void>; readOnly?: boolean }) {
  const suppliers = useFetch<Page<Supplier>>("/suppliers", { page_size: 100 });
  const { register, control, handleSubmit, formState: { errors, isSubmitting } } = useForm<POValues>({ resolver: zodResolver(schema), values: initial });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const items = useWatch({ control, name: "items" });
  // Display-only preview; the server recomputes totals with Decimal on save.
  const preview = (items ?? []).reduce((acc, i) => {
    const base = (Number(i.quantity) || 0) * (Number(i.unit_price) || 0);
    return { sub: acc.sub + base, tax: acc.tax + base * (Number(i.tax_rate) || 0) / 100 };
  }, { sub: 0, tax: 0 });
  const ro = { disabled: readOnly };

  return (
    <form className="space-y-5" noValidate onSubmit={handleSubmit((v) => onSubmit({
      ...v, expected_delivery_date: v.expected_delivery_date || null, notes: v.notes || null,
      items: v.items.map((i) => ({ ...i, hsn_sac: i.hsn_sac || null, unit: i.unit || null })),
    }))}>
      <Card>
        <CardHeader><CardTitle>Purchase order</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Supplier" error={errors.supplier_id?.message}>
            <Select {...register("supplier_id")} {...ro}><option value="">Select…</option>{suppliers.data?.items.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
          </Field>
          <Field label="PO number" error={errors.po_number?.message}><Input {...register("po_number")} {...ro} /></Field>
          <Field label="Status"><Select {...register("status")} {...ro}><option value="draft">Draft</option><option value="open">Open</option><option value="partially_invoiced">Partially invoiced</option><option value="closed">Closed</option><option value="cancelled">Cancelled</option></Select></Field>
          <Field label="PO date" error={errors.po_date?.message}><Input type="date" {...register("po_date")} {...ro} /></Field>
          <Field label="Expected delivery"><Input type="date" {...register("expected_delivery_date")} {...ro} /></Field>
          <Field label="Notes" className="lg:col-span-1 sm:col-span-2"><Textarea rows={1} {...register("notes")} {...ro} /></Field>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Items</CardTitle>
          {!readOnly && <Button type="button" size="sm" variant="outline" onClick={() => append({ description: "", hsn_sac: "", quantity: "1", unit: "Nos", unit_price: "0", tax_rate: "18" })}><Plus /> Add line</Button>}
        </CardHeader>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-surface-muted/60 text-xs text-muted-foreground"><tr>{["#", "Description", "HSN/SAC", "Qty", "Unit", "Unit price", "GST %", ""].map((h) => <th key={h} className="px-2 py-2 text-left font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y">
              {fields.map((f, i) => (
                <tr key={f.id}>
                  <td className="num px-2 text-muted-foreground">{i + 1}</td>
                  <td className="px-1 py-1.5"><Input className="h-8 min-w-60" aria-invalid={!!errors.items?.[i]?.description} {...register(`items.${i}.description`)} {...ro} /></td>
                  {(["hsn_sac", "quantity", "unit", "unit_price", "tax_rate"] as const).map((k) => (
                    <td key={k} className="px-1 py-1.5"><Input className="num h-8 w-24" aria-label={`Line ${i + 1} ${k}`} aria-invalid={!!errors.items?.[i]?.[k]} title={errors.items?.[i]?.[k]?.message} {...register(`items.${i}.${k}`)} {...ro} /></td>
                  ))}
                  <td>{!readOnly && fields.length > 1 && <Button type="button" variant="ghost" size="icon" onClick={() => remove(i)} aria-label={`Remove line ${i + 1}`}><Trash2 className="text-muted-foreground" /></Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="num flex justify-end gap-6 border-t px-5 py-3 text-sm">
          <span className="text-muted-foreground">Subtotal {money(preview.sub)}</span>
          <span className="text-muted-foreground">Tax {money(preview.tax)}</span>
          <span className="font-semibold">Total {money(preview.sub + preview.tax)}</span>
        </div>
      </Card>
      {!readOnly && <div className="flex justify-end"><Button type="submit" loading={isSubmitting}>Save purchase order</Button></div>}
    </form>
  );
}
