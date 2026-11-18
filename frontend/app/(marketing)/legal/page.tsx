import type { Metadata } from "next";
import { PageIntro, Section } from "@/components/marketing/sections";

export const metadata: Metadata = { title: "Legal" };

export default function Legal() {
  return (
    <>
      <PageIntro eyebrow="Legal" title="Privacy, terms and security" intro="Plain-language summary for this portfolio MVP. A production deployment needs reviewed legal documents." />
      <Section id="privacy" title="Privacy notice">
        <p className="max-w-3xl text-sm text-muted-foreground">Documents and extracted data are stored in the database and storage you configure. LedgerFlow does not send documents to third parties unless an administrator explicitly enables the optional cloud AI provider. Demo data is synthetic.</p>
      </Section>
      <Section id="terms" title="Terms of use" className="pt-0">
        <p className="max-w-3xl text-sm text-muted-foreground">Validation results are decision support. Users remain responsible for verifying invoices and tax treatment before payment. GSTIN checks are offline format checks, not GST portal verification.</p>
      </Section>
      <Section id="security" title="Security" className="pt-0">
        <p className="max-w-3xl text-sm text-muted-foreground">Passwords are hashed with bcrypt; sessions use signed, httpOnly cookies that are revoked on logout; every API request is authorised server-side and scoped to one company; uploads are verified by content; audit entries are append-only. Report vulnerabilities via the contact page.</p>
      </Section>
    </>
  );
}
