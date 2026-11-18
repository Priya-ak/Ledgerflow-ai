import type { Metadata } from "next";
import { CtaBand, PageIntro, Section, Workflow } from "@/components/marketing/sections";

export const metadata: Metadata = { title: "How it works" };

const STATUSES = ["Processing", "Extracted / Needs review", "Pending approval", "Approved or Rejected"];

export default function HowItWorks() {
  return (
    <>
      <PageIntro eyebrow="How it works" title="A transparent pipeline you can explain to an auditor"
        intro="Each step produces a stored, inspectable result: the original file, the extracted JSON, the validation report, the PO comparison and every decision." />
      <Section title="The six steps"><Workflow /></Section>
      <Section title="Invoice lifecycle" className="pt-0" intro="Invoices with problems are routed to review instead of being silently corrected.">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {STATUSES.map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              <span className="rounded-lg border bg-surface px-3 py-2">{s}</span>
              {i < STATUSES.length - 1 && <span className="text-muted-foreground">→</span>}
            </span>
          ))}
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {[
            ["What the validation engine checks", "Required fields, dates, GSTIN format and check digit, quantities, line taxable value, line tax, line totals, subtotal, discount, taxable total, CGST/SGST/IGST regime, total tax, grand total and supplier consistency."],
            ["How duplicates are detected", "Same supplier and normalised invoice number, identical document checksum, or the same amount and date from the same supplier — each with a score and a reason."],
            ["How PO matching works", "Invoice lines are paired with PO lines by HSN/SAC and description similarity, then quantity, unit price, tax rate and amount are compared within tolerances."],
          ].map(([t, b]) => <div key={t} className="rounded-xl border bg-surface p-5"><h3 className="text-sm font-semibold">{t}</h3><p className="mt-2 text-sm text-muted-foreground">{b}</p></div>)}
        </div>
      </Section>
      <CtaBand />
    </>
  );
}
