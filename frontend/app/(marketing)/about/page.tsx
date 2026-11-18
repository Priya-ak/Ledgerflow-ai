import type { Metadata } from "next";
import { CtaBand, PageIntro, Section } from "@/components/marketing/sections";

export const metadata: Metadata = { title: "About" };

export default function About() {
  return (
    <>
      <PageIntro eyebrow="About" title="Practical automation for finance teams"
        intro="LedgerFlow AI was built to show how document AI can remove repetitive data entry without handing financial decisions to a model." />
      <Section title="Our principles">
        <div className="grid gap-4 md:grid-cols-3">
          {[
            ["Deterministic where it matters", "Money is calculated with exact decimals and explicit rules. Every check states the expected value, the actual value and the difference."],
            ["Humans decide", "AI can read and suggest. People review, correct and approve, and the system records who did what."],
            ["Runs on modest hardware", "Designed for a Windows laptop with 4 GB of RAM: one process each for backend and frontend, one document at a time, no GPU."],
          ].map(([t, b]) => <div key={t} className="rounded-xl border bg-surface p-5"><h3 className="text-sm font-semibold">{t}</h3><p className="mt-2 text-sm text-muted-foreground">{b}</p></div>)}
        </div>
      </Section>
      <Section title="Who it is for" className="pt-0">
        <p className="max-w-3xl text-muted-foreground">Manufacturers, distributors, trading companies, CA and bookkeeping firms, and any business that receives GST invoices from many suppliers and needs a reliable, auditable path from document to payment approval.</p>
      </Section>
      <CtaBand />
    </>
  );
}
