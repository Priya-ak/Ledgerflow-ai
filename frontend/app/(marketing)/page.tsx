import { ArrowRight, FileWarning, Hourglass, Repeat } from "lucide-react";
import Link from "next/link";
import { CtaBand, Faq, FeatureGrid, Pricing, ProductPreview, Section, Workflow } from "@/components/marketing/sections";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <>
      <section className="border-b bg-surface">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:py-24">
          <div>
            <p className="inline-flex items-center rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground">
              Accounts payable automation for Indian GST invoices
            </p>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
              From supplier invoice to approved payable — <span className="text-primary">checked, matched and audited.</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg text-muted-foreground">
              LedgerFlow AI reads PDFs and scans, extracts every field, verifies GST arithmetic to the paisa, catches duplicates,
              matches purchase orders and routes invoices to the right approver.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button size="lg" asChild><Link href="/login?demo=1">Try the live demo <ArrowRight /></Link></Button>
              <Button size="lg" variant="outline" asChild><Link href="/how-it-works">How it works</Link></Button>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">Runs on a 4 GB laptop. No GPU, no paid APIs, no AI model required.</p>
          </div>
          <ProductPreview />
        </div>
      </section>

      <Section eyebrow="The problem" title="Manual invoice entry is slow, repetitive and error-prone"
        intro="Finance teams re-key supplier invoices, recalculate GST by hand, check purchase orders in another system and chase approvals over email.">
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { icon: Hourglass, t: "Hours of data entry", b: "Each invoice is typed into a spreadsheet or ERP line by line, then checked again by someone else." },
            { icon: FileWarning, t: "Errors slip through", b: "Wrong tax rates, CGST charged on inter-state supplies and arithmetic mistakes are easy to miss." },
            { icon: Repeat, t: "Duplicates get paid", b: "The same invoice arrives by email and courier. Without a check, it is processed twice." },
          ].map((p) => (
            <div key={p.t} className="rounded-xl border bg-surface p-6">
              <p.icon className="size-5 text-warning" /><h3 className="mt-4 text-sm font-semibold">{p.t}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{p.b}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="The solution" title="One pipeline from document to decision" className="pt-0"
        intro="Every invoice follows the same transparent path. Machines do the reading and arithmetic; people make the decisions.">
        <Workflow />
      </Section>

      <div className="border-y bg-surface">
        <Section eyebrow="Capabilities" title="Built for accuracy, not demos" intro="AI where it helps, deterministic rules where money is involved.">
          <FeatureGrid limit={6} />
          <div className="mt-6"><Button variant="link" asChild><Link href="/features">See all features <ArrowRight /></Link></Button></div>
        </Section>
      </div>

      <Section eyebrow="Approvals & security" title="Controls your auditors will recognise">
        <div className="grid gap-6 md:grid-cols-2">
          {[
            ["Segregation of duties", "Accountants prepare, approvers decide. Nobody approves their own submission or two levels of the same invoice."],
            ["Critical errors block approval", "An invoice with failed arithmetic or tax checks cannot be approved until it is corrected."],
            ["Server-side authorisation", "Every API call checks identity, role and company membership. The browser never holds service credentials."],
            ["Immutable audit log", "Who did what, when, and what changed — including manual corrections and report exports."],
          ].map(([t, b]) => (
            <div key={t} className="border-l-2 border-primary pl-4"><h3 className="text-sm font-semibold">{t}</h3><p className="mt-1 text-sm text-muted-foreground">{b}</p></div>
          ))}
        </div>
      </Section>

      <div className="border-y bg-surface">
        <Section eyebrow="Pricing" title="Simple, transparent plans"><Pricing /></Section>
      </div>
      <Section eyebrow="FAQ" title="Questions finance teams ask"><Faq limit={5} /></Section>
      <CtaBand />
    </>
  );
}
