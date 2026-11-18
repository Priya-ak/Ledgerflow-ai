import type { Metadata } from "next";
import { Faq, PageIntro, Pricing, Section } from "@/components/marketing/sections";

export const metadata: Metadata = { title: "Pricing" };

export default function PricingPage() {
  return (
    <>
      <PageIntro eyebrow="Pricing" title="Start free on your own machine" intro="Self-host at no cost, or choose a hosted plan when your team is ready." />
      <Section title="Plans"><Pricing /></Section>
      <Section title="Frequently asked" className="pt-0"><Faq limit={4} /></Section>
    </>
  );
}
