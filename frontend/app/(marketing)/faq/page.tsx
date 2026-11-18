import type { Metadata } from "next";
import { Faq, PageIntro, Section } from "@/components/marketing/sections";

export const metadata: Metadata = { title: "FAQ" };

export default function FaqPage() {
  return (
    <>
      <PageIntro eyebrow="FAQ" title="Frequently asked questions" intro="How LedgerFlow handles documents, AI, validation and approvals." />
      <Section title="Answers"><Faq /></Section>
    </>
  );
}
