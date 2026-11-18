"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { InvoiceListItem } from "@/lib/types";
import { date, money } from "@/lib/utils";

export function InvoiceTable({ items, compact }: { items: InvoiceListItem[]; compact?: boolean }) {
  return (
    <Table>
      <THead>
        <tr>
          <TH>Invoice</TH><TH>Supplier</TH><TH>Date</TH><TH className="text-right">Amount</TH><TH>Status</TH>
          {!compact && <><TH>Validation</TH><TH>Duplicate</TH><TH>PO match</TH></>}
        </tr>
      </THead>
      <TBody>
        {items.map((i) => (
          <TR key={i.id}>
            <TD>
              <Link href={`/app/invoices/${i.id}`} className="font-medium text-primary hover:underline">{i.invoice_number ?? "Untitled invoice"}</Link>
              {i.is_demo && <span className="ml-2 text-[10px] uppercase text-muted-foreground">demo</span>}
            </TD>
            <TD className="max-w-48 truncate">{i.supplier?.name ?? <span className="text-muted-foreground">{i.supplier_name_raw ?? "Unmatched"}</span>}</TD>
            <TD className="num whitespace-nowrap text-muted-foreground">{date(i.invoice_date)}</TD>
            <TD className="num whitespace-nowrap text-right font-medium">{money(i.grand_total)}</TD>
            <TD><StatusBadge value={i.status} /></TD>
            {!compact && (
              <>
                <TD><span className="inline-flex items-center gap-1"><StatusBadge value={i.validation_status} />{i.has_critical_errors && <AlertTriangle className="size-3.5 text-danger" aria-label="Critical errors" />}</span></TD>
                <TD><StatusBadge value={i.duplicate_status} /></TD>
                <TD><StatusBadge value={i.po_match_status} /></TD>
              </>
            )}
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
