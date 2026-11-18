"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import type { InvoiceDetail, Page, PurchaseOrder, Supplier } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { cn } from "@/lib/utils";

const dec = z.string().trim().regex(/^$|^-?\d+(\.\d{1,3})?$/, "Number, up to 3 decimals").optional();
const gstin = z.string().trim().toUpperCase().regex(/^$|^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/, "Invalid GSTIN format").optional();

const itemSchema = z.object({
  description: z.string().max(500).optional(), hsn_sac: z.string().regex(/^$|^\d{4,8}$/, "4–8 digits").optional(),
  quantity: dec, unit: z.string().max(20).optional(), unit_price: dec, discount: dec, taxable_value: dec, tax_rate: dec, tax_amount: dec, line_total: dec,
});

export const invoiceSchema = z.object({
  supplier_id: z.string().optional(), purchase_order_id: z.string().optional(),
  invoice_number: z.string().max(60).optional(), invoice_date: z.string().optional(), due_date: z.string().optional(),
  po_number_ref: z.string().max(60).optional(), currency: z.string().length(3),
  supplier_name_raw: z.string().max(200).optional(), supplier_gstin_raw: gstin, supplier_address_raw: z.string().max(1000).optional(),
  buyer_name: z.string().max(200).optional(), buyer_gstin: gstin, buyer_address: z.string().max(1000).optional(),
  subtotal: dec, discount: dec, taxable_amount: dec, cgst: dec, sgst: dec, igst: dec, other_charges: dec, total_tax: dec, grand_total: dec,
  payment_status: z.enum(["unpaid", "partially_paid", "paid"]), notes: z.string().max(2000).optional(),
  items: z.array(itemSchema).max(200),
});
export type InvoiceFormValues = z.infer<typeof invoiceSchema>;

const s = (v: string | null | undefined) => v ?? "";
const ITEM_KEYS = ["description", "hsn_sac", "quantity", "unit", "unit_price", "discount", "taxable_value", "tax_rate", "tax_amount", "line_total"] as const;

export function toFormValues(inv?: InvoiceDetail | null): InvoiceFormValues {
  return {
    supplier_id: s(inv?.supplier_id), purchase_order_id: s(inv?.purchase_order_id), invoice_number: s(inv?.invoice_number),
    invoice_date: s(inv?.invoice_date), due_date: s(inv?.due_date), po_number_ref: s(inv?.po_number_ref), currency: inv?.currency ?? "INR",
    supplier_name_raw: s(inv?.supplier_name_raw), supplier_gstin_raw: s(inv?.supplier_gstin_raw), supplier_address_raw: s(inv?.supplier_address_raw),
    buyer_name: s(inv?.buyer_name), buyer_gstin: s(inv?.buyer_gstin), buyer_address: s(inv?.buyer_address),
    subtotal: s(inv?.subtotal), discount: s(inv?.discount), taxable_amount: s(inv?.taxable_amount), cgst: s(inv?.cgst), sgst: s(inv?.sgst),
    igst: s(inv?.igst), other_charges: s(inv?.other_charges), total_tax: s(inv?.total_tax), grand_total: s(inv?.grand_total),
    payment_status: (inv?.payment_status as InvoiceFormValues["payment_status"]) ?? "unpaid", notes: s(inv?.notes),
    items: (inv?.items ?? []).map((it) => Object.fromEntries(ITEM_KEYS.map((k) => [k, s(it[k])])) as InvoiceFormValues["items"][number]),
  };
}

/** Empty strings become null so the API stores "missing", never "0". */
export function toPayload(v: InvoiceFormValues) {
  const nul = (x: string | undefined) => (x === undefined || x.trim() === "" ? null : x.trim());
  const out: Record<string, unknown> = {};
  for (const [k, val] of Object.entries(v)) {
    if (k === "items") continue;
    out[k] = typeof val === "string" ? nul(val) : val;
  }
  out.currency = v.currency;
  out.payment_status = v.payment_status;
  out.items = v.items.map((it) => Object.fromEntries(Object.entries(it).map(([k, x]) => [k, nul(x as string | undefined)])));
  return out;
}

export function InvoiceForm({ initial, readOnly, reviewFields = [], onSubmit, submitLabel, formId }: {
  initial: InvoiceFormValues; readOnly?: boolean; reviewFields?: string[]; onSubmit: (v: InvoiceFormValues) => Promise<void>; submitLabel: string; formId: string;
}) {
  const suppliers = useFetch<Page<Supplier>>("/suppliers", { page_size: 100 });
  const pos = useFetch<Page<PurchaseOrder>>("/purchase-orders", { page_size: 100 });
  const { register, control, handleSubmit, setValue, formState: { errors, isSubmitting, isDirty } } = useForm<InvoiceFormValues>({ resolver: zodResolver(invoiceSchema), values: initial });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  // The <option> lists load after the form is initialised. A native <select> cannot show a value that has no
  // matching <option> yet, so it would display "Not linked" for an invoice that IS linked. Re-apply the saved
  // links once the lists exist (the stored link itself was never affected).
  const listsReady = !suppliers.loading && !pos.loading;
  useEffect(() => {
    if (!listsReady) return;
    setValue("supplier_id", initial.supplier_id ?? "");
    setValue("purchase_order_id", initial.purchase_order_id ?? "");
  }, [listsReady, initial.supplier_id, initial.purchase_order_id, setValue]);
  const flag = (key: string) => reviewFields.some((f) => f === key || f.endsWith(`.${key}`));
  const hl = (key: string) => (flag(key) ? "border-warning ring-2 ring-warning/25" : "");
  const ro = { disabled: readOnly };

  return (
    <form id={formId} onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
      <Card>
        <CardHeader><div><CardTitle>Invoice</CardTitle>{reviewFields.length > 0 && !readOnly && <CardDescription className="text-warning">Highlighted fields could not be read confidently. Check them against the document.</CardDescription>}</div></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Field label="Invoice number" error={errors.invoice_number?.message}><Input className={hl("invoice_number")} {...register("invoice_number")} {...ro} /></Field>
          <Field label="Invoice date" error={errors.invoice_date?.message}><Input type="date" className={hl("invoice_date")} {...register("invoice_date")} {...ro} /></Field>
          <Field label="Due date"><Input type="date" {...register("due_date")} {...ro} /></Field>
          <Field label="Supplier (master data)" hint="Linking is required before submission.">
            <Select className={hl("name")} {...register("supplier_id")} {...ro}>
              <option value="">— Not linked —</option>
              {suppliers.data?.items.map((x) => <option key={x.id} value={x.id}>{x.name} ({x.code})</option>)}
            </Select>
          </Field>
          <Field label="Purchase order">
            <Select {...register("purchase_order_id")} {...ro}>
              <option value="">— None —</option>
              {pos.data?.items.map((p) => <option key={p.id} value={p.id}>{p.po_number} · {p.supplier.name}</option>)}
            </Select>
          </Field>
          <Field label="PO number on invoice"><Input {...register("po_number_ref")} {...ro} /></Field>
          <Field label="Payment status">
            <Select {...register("payment_status")} {...ro}><option value="unpaid">Unpaid</option><option value="partially_paid">Partially paid</option><option value="paid">Paid</option></Select>
          </Field>
          <Field label="Currency"><Input maxLength={3} className="uppercase" {...register("currency")} {...ro} /></Field>
        </CardContent>
      </Card>

      <div className="grid gap-5 2xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Supplier as printed</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <Field label="Name"><Input className={hl("supplier.name")} {...register("supplier_name_raw")} {...ro} /></Field>
            <Field label="GSTIN" error={errors.supplier_gstin_raw?.message}><Input className={cn("uppercase", hl("supplier.gstin"))} maxLength={15} {...register("supplier_gstin_raw")} {...ro} /></Field>
            <Field label="Address"><Textarea rows={2} {...register("supplier_address_raw")} {...ro} /></Field>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Buyer</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <Field label="Name"><Input className={hl("buyer.name")} {...register("buyer_name")} {...ro} /></Field>
            <Field label="GSTIN" error={errors.buyer_gstin?.message}><Input className={cn("uppercase", hl("buyer.gstin"))} maxLength={15} {...register("buyer_gstin")} {...ro} /></Field>
            <Field label="Address"><Textarea rows={2} {...register("buyer_address")} {...ro} /></Field>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div><CardTitle>Line items</CardTitle><CardDescription>Amounts as printed. Validation recalculates every line independently.</CardDescription></div>
          {!readOnly && <Button type="button" size="sm" variant="outline" onClick={() => append({ description: "", hsn_sac: "", quantity: "", unit: "", unit_price: "", discount: "0", taxable_value: "", tax_rate: "18", tax_amount: "", line_total: "" })}><Plus /> Add line</Button>}
        </CardHeader>
        <div className={cn("overflow-x-auto", flag("items") && "ring-2 ring-inset ring-warning/30")}>
          <table className="w-full min-w-[980px] text-sm">
            <thead className="bg-surface-muted/60 text-xs text-muted-foreground">
              <tr>{["#", "Description", "HSN/SAC", "Qty", "Unit", "Unit price", "Discount", "Taxable", "GST %", "Tax", "Line total", ""].map((h) => <th key={h} className="px-2 py-2 text-left font-medium">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y">
              {fields.map((f, i) => (
                <tr key={f.id}>
                  <td className="num px-2 py-1.5 text-muted-foreground">{i + 1}</td>
                  <td className="px-1 py-1.5"><Input className="h-8 min-w-52" {...register(`items.${i}.description`)} {...ro} /></td>
                  {(["hsn_sac", "quantity", "unit", "unit_price", "discount", "taxable_value", "tax_rate", "tax_amount", "line_total"] as const).map((k) => (
                    <td key={k} className="px-1 py-1.5">
                      <Input className={cn("num h-8", k === "unit" || k === "tax_rate" ? "w-16" : "w-24", errors.items?.[i]?.[k] && "border-danger")} inputMode={k === "unit" ? "text" : "decimal"}
                        aria-label={`Line ${i + 1} ${k}`} title={errors.items?.[i]?.[k]?.message} {...register(`items.${i}.${k}`)} {...ro} />
                    </td>
                  ))}
                  <td className="px-1">{!readOnly && <Button type="button" variant="ghost" size="icon" onClick={() => remove(i)} aria-label={`Remove line ${i + 1}`}><Trash2 className="text-muted-foreground" /></Button>}</td>
                </tr>
              ))}
              {fields.length === 0 && <tr><td colSpan={12} className="px-4 py-6 text-center text-sm text-muted-foreground">No line items captured.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-5 2xl:grid-cols-[1fr_1.2fr]">
        <Card>
          <CardHeader><CardTitle>Notes</CardTitle></CardHeader>
          <CardContent><Textarea rows={6} placeholder="Internal notes (e.g. GRN reference)" {...register("notes")} {...ro} /></CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Summary</CardTitle></CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-3">
            {([["subtotal", "Subtotal"], ["discount", "Discount"], ["taxable_amount", "Taxable amount"], ["cgst", "CGST"], ["sgst", "SGST"], ["igst", "IGST"], ["other_charges", "Other charges"], ["total_tax", "Total tax"], ["grand_total", "Grand total"]] as const).map(([k, label]) => (
              <Field key={k} label={label} error={errors[k]?.message}>
                <Input inputMode="decimal" className={cn("num", k === "grand_total" && "font-semibold", hl(k === "taxable_amount" ? "taxable_total" : k))} {...register(k)} {...ro} />
              </Field>
            ))}
          </CardContent>
        </Card>
      </div>

      {!readOnly && (
        <div className="sticky bottom-0 z-10 -mx-1 flex justify-end gap-2 border-t bg-background/95 px-1 py-3 backdrop-blur">
          {isDirty && <span className="mr-auto self-center text-xs text-warning">Unsaved changes</span>}
          <Button type="submit" loading={isSubmitting}>{submitLabel}</Button>
        </div>
      )}
    </form>
  );
}
