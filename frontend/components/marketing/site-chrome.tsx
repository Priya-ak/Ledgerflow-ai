"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/features", label: "Features" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/about", label: "About" },
  { href: "/faq", label: "FAQ" },
  { href: "/contact", label: "Contact" },
];

export function SiteHeader() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" aria-label="LedgerFlow AI home"><Logo /></Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href}
              className={cn("rounded-md px-3 py-2 text-sm text-muted-foreground hover:text-foreground", path === n.href && "text-foreground font-medium")}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          <ThemeToggle />
          <Button variant="ghost" asChild><Link href="/login">Sign in</Link></Button>
          <Button asChild><Link href="/login?demo=1">Try the demo</Link></Button>
        </div>
        <button className="md:hidden rounded-md p-2" onClick={() => setOpen(!open)} aria-label="Toggle menu" aria-expanded={open}>
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </div>
      {open && (
        <div className="border-t bg-surface px-4 py-3 md:hidden">
          {NAV.map((n) => <Link key={n.href} href={n.href} onClick={() => setOpen(false)} className="block rounded-md px-2 py-2 text-sm">{n.label}</Link>)}
          <div className="mt-2 flex gap-2">
            <Button variant="outline" className="flex-1" asChild><Link href="/login">Sign in</Link></Button>
            <Button className="flex-1" asChild><Link href="/login?demo=1">Try the demo</Link></Button>
          </div>
        </div>
      )}
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t bg-surface">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-4">
        <div className="space-y-3">
          <Logo />
          <p className="text-sm text-muted-foreground">Intelligent invoice processing and business document management for finance teams.</p>
        </div>
        <FooterCol title="Product" links={[["/features", "Features"], ["/how-it-works", "How it works"], ["/pricing", "Pricing"], ["/login?demo=1", "Live demo"]]} />
        <FooterCol title="Company" links={[["/about", "About"], ["/contact", "Contact"], ["/faq", "FAQ"]]} />
        <FooterCol title="Legal" links={[["/legal#privacy", "Privacy notice"], ["/legal#terms", "Terms of use"], ["/legal#security", "Security"]]} />
      </div>
      <div className="border-t">
        <p className="mx-auto max-w-6xl px-4 py-5 text-xs text-muted-foreground sm:px-6">
          © {new Date().getFullYear()} LedgerFlow AI. Portfolio project. GSTIN checks are format checks only and are not a substitute for GST portal verification.
        </p>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <p className="text-sm font-semibold">{title}</p>
      <ul className="mt-3 space-y-2">
        {links.map(([href, label]) => <li key={href}><Link href={href} className="text-sm text-muted-foreground hover:text-foreground">{label}</Link></li>)}
      </ul>
    </div>
  );
}
