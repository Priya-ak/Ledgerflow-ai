import type { Metadata } from "next";
import { CtaBand, FeatureGrid, PageIntro, Section } from "@/components/marketing/sections";

export const metadata: Metadata = { title: "Features" };

export default function Features() {
  return (
    <>
      <PageIntro eyebrow="Features" title="Everything between “invoice received” and “approved for payment”"
        intro="LedgerFlow combines document processing, financial validation and workflow controls in one modular application." />
      <Section title="Core capabilities"><FeatureGrid /></Section>
      <Section title="What runs where" className="pt-0">
        <div className="overflow-hidden rounded-xl border bg-surface text-sm">
          {[
            ["Text extraction", "PyMuPDF (digital PDF) · Tesseract OCR (scans/images)", "Local"],
            ["Field extraction", "Rule-based patterns + Pydantic schema", "Local, deterministic"],
            ["Optional AI assist", "Qwen 2.5 0.5B via Ollama (identifiers only, grounded)", "Local, optional"],
            ["Financial validation", "Python Decimal engine with tolerances", "Local, deterministic"],
            ["Duplicates & PO matching", "Database rules and line comparison", "Local, deterministic"],
            ["Approval decisions", "Authorised people only", "Human"],
          ].map(([a, b, c]) => (
            <div key={a} className="grid grid-cols-1 gap-1 border-b px-5 py-3 last:border-0 sm:grid-cols-[1fr_2fr_1fr]">
              <span className="font-medium">{a}</span><span className="text-muted-foreground">{b}</span><span className="text-muted-foreground">{c}</span>
            </div>
          ))}
        </div>
      </Section>
      <CtaBand />
    </>
  );
}
