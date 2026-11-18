import type { Metadata } from "next";
import { PageIntro, Section } from "@/components/marketing/sections";
import { ContactForm } from "./contact-form";

export const metadata: Metadata = { title: "Contact" };

export default function Contact() {
  return (
    <>
      <PageIntro eyebrow="Contact" title="Talk to us about your invoice workflow" intro="Tell us about your volume, document types and approval process." />
      <Section title="Send a message">
        <div className="grid gap-10 md:grid-cols-[1.3fr_1fr]">
          <ContactForm />
          <div className="space-y-4 text-sm text-muted-foreground">
            <p>This MVP has no outbound email service configured. Submitting the form opens your own email client with the message pre-filled, so nothing is lost or silently dropped.</p>
            <p>For a hands-on look, the demo workspace is available with synthetic data.</p>
          </div>
        </div>
      </Section>
    </>
  );
}
