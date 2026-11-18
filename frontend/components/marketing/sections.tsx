import { ArrowRight, Check, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { FAQS, FEATURES, PLANS, STEPS } from "./content";

export function Section({ eyebrow, title, intro, children, className, id }: { eyebrow?: string; title: string; intro?: string; children: React.ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn("mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-20", className)}>
      <div className="max-w-2xl">
        {eyebrow && <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">{eyebrow}</p>}
        <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h2>
        {intro && <p className="mt-3 text-muted-foreground">{intro}</p>}
      </div>
      <div className="mt-10">{children}</div>
    </section>
  );
}

export function PageIntro({ eyebrow, title, intro }: { eyebrow: string; title: string; intro: string }) {
  return (
    <div className="border-b bg-surface">
      <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">{eyebrow}</p>
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-4 max-w-2xl text-muted-foreground">{intro}</p>
      </div>
    </div>
  );
}

export function FeatureGrid({ limit }: { limit?: number }) {
  return (
    <div className="grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-2 lg:grid-cols-3">
      {FEATURES.slice(0, limit).map((f) => (
        <div key={f.title} className="bg-surface p-6">
          <f.icon className="size-5 text-primary" aria-hidden />
          <h3 className="mt-4 text-sm font-semibold">{f.title}</h3>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
        </div>
      ))}
    </div>
  );
}

export function Workflow() {
  return (
    <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {STEPS.map((s, i) => (
        <li key={s.title} className="rounded-xl border bg-surface p-5">
          <div className="flex items-center gap-3">
            <span className="num flex size-7 items-center justify-center rounded-full bg-primary-soft text-xs font-semibold text-primary">{i + 1}</span>
            <h3 className="text-sm font-semibold">{s.title}</h3>
          </div>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
        </li>
      ))}
    </ol>
  );
}

export function Pricing() {
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-3">
        {PLANS.map((p) => (
          <div key={p.name} className={cn("flex flex-col rounded-xl border bg-surface p-6", p.highlight && "border-primary ring-1 ring-primary")}>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{p.name}</h3>
              {p.highlight && <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-medium text-primary">Most popular</span>}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{p.tagline}</p>
            <p className="mt-5"><span className="num text-3xl font-semibold">{p.price}</span> <span className="text-sm text-muted-foreground">{p.period}</span></p>
            <ul className="mt-5 flex-1 space-y-2.5">
              {p.features.map((f) => <li key={f} className="flex gap-2 text-sm"><Check className="mt-0.5 size-4 shrink-0 text-primary" />{f}</li>)}
            </ul>
            <Button className="mt-6" variant={p.highlight ? "default" : "outline"} asChild>
              <Link href={p.cta === "Try the demo" ? "/login?demo=1" : "/contact"}>{p.cta}</Link>
            </Button>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-muted-foreground">Pricing is presentation-only for this MVP. No payment provider is connected and nothing is billed.</p>
    </>
  );
}

export function Faq({ limit }: { limit?: number }) {
  return (
    <div className="divide-y rounded-xl border bg-surface">
      {FAQS.slice(0, limit).map((f) => (
        <details key={f.q} className="group px-5 py-4">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium">
            {f.q}<span className="text-muted-foreground transition-transform group-open:rotate-45" aria-hidden>+</span>
          </summary>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
        </details>
      ))}
    </div>
  );
}

/** Static illustration of a validation report (labelled as such, not live data). */
export function ProductPreview() {
  const rows = [
    { icon: CheckCircle2, cls: "text-success", name: "Line taxable values", detail: "3 of 3 lines match qty × rate − discount" },
    { icon: XCircle, cls: "text-danger", name: "Line 2 tax amount", detail: "Expected ₹6,408.00 · found ₹4,272.00 · diff −₹2,136.00" },
    { icon: CheckCircle2, cls: "text-success", name: "GST regime", detail: "Inter-state supply — IGST applied" },
    { icon: AlertTriangle, cls: "text-warning", name: "Purchase order", detail: "Unit price 3.4% above PO-2026-0106" },
  ];
  return (
    <div className="relative">
      <div className="rounded-2xl border bg-surface p-2 shadow-[0_20px_60px_-25px_rgba(15,23,42,0.35)]">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <p className="text-xs text-muted-foreground">Invoice DOS-INV-88213 · Deccan Office Supplies</p>
            <p className="num text-lg font-semibold">₹95,872.00</p>
          </div>
          <span className="rounded-md bg-danger-soft px-2 py-1 text-xs font-medium text-danger">1 critical issue</span>
        </div>
        <ul className="divide-y">
          {rows.map((r) => (
            <li key={r.name} className="flex gap-3 px-4 py-3">
              <r.icon className={cn("mt-0.5 size-4 shrink-0", r.cls)} />
              <div><p className="text-sm font-medium">{r.name}</p><p className="num text-xs text-muted-foreground">{r.detail}</p></div>
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">Illustration based on the bundled synthetic sample invoice.</p>
    </div>
  );
}

export function CtaBand() {
  return (
    <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
      <div className="flex flex-col items-start justify-between gap-6 rounded-2xl bg-primary px-8 py-10 text-primary-foreground sm:flex-row sm:items-center">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">See the full workflow in five minutes</h2>
          <p className="mt-2 opacity-85">Sign in as an accountant or approver with synthetic invoices preloaded.</p>
        </div>
        <Button size="lg" variant="outline" className="border-white/30 bg-white text-slate-900 hover:bg-white/90" asChild>
          <Link href="/login?demo=1">Open the demo <ArrowRight /></Link>
        </Button>
      </div>
    </section>
  );
}
