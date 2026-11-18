"use client";

import {
  BarChart3, Building2, CheckSquare, FileStack, FileText, FolderOpen, LayoutDashboard, LogOut, Menu, ScrollText, Settings,
  ShoppingCart, Truck, Upload, Users, X, type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/feedback";
import { useSession } from "@/lib/session";
import { cn, humanize } from "@/lib/utils";

type NavItem = { href: string; label: string; icon: LucideIcon; perm?: string; exact?: boolean };
const GROUPS: { label?: string; items: NavItem[] }[] = [
  { items: [{ href: "/app", label: "Dashboard", icon: LayoutDashboard, exact: true }] },
  {
    label: "Payables",
    items: [
      { href: "/app/invoices/upload", label: "Upload invoices", icon: Upload, perm: "documents:upload" },
      { href: "/app/invoices", label: "Invoices", icon: FileText, perm: "invoices:read" },
      { href: "/app/approvals", label: "Approvals", icon: CheckSquare, perm: "approvals:read" },
      { href: "/app/documents", label: "Documents", icon: FolderOpen, perm: "documents:read" },
    ],
  },
  {
    label: "Master data",
    items: [
      { href: "/app/suppliers", label: "Suppliers", icon: Truck, perm: "suppliers:read" },
      { href: "/app/purchase-orders", label: "Purchase orders", icon: ShoppingCart, perm: "po:read" },
    ],
  },
  {
    label: "Insights",
    items: [
      { href: "/app/analytics", label: "Analytics", icon: BarChart3, perm: "analytics:read" },
      { href: "/app/reports", label: "Reports & export", icon: FileStack, perm: "reports:export" },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/app/admin/users", label: "Users", icon: Users, perm: "users:manage" },
      { href: "/app/admin/settings", label: "Company & policy", icon: Settings, perm: "settings:manage" },
      { href: "/app/admin/audit", label: "Audit log", icon: ScrollText, perm: "audit:read" },
    ],
  },
];

function isActive(path: string, item: NavItem) {
  if (item.exact) return path === item.href;
  if (item.href === "/app/invoices") return path.startsWith("/app/invoices") && !path.startsWith("/app/invoices/upload");
  return path.startsWith(item.href);
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  const { can } = useSession();
  return (
    <nav className="space-y-5" aria-label="Application">
      {GROUPS.map((g, i) => {
        const items = g.items.filter((it) => !it.perm || can(it.perm));
        if (!items.length) return null;
        return (
          <div key={i}>
            {g.label && <p className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">{g.label}</p>}
            <ul className="space-y-0.5">
              {items.map((it) => {
                const active = isActive(path, it);
                return (
                  <li key={it.href}>
                    <Link href={it.href} onClick={onNavigate} aria-current={active ? "page" : undefined}
                      className={cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                        active ? "bg-primary-soft font-medium text-primary" : "text-muted-foreground hover:bg-surface-muted hover:text-foreground")}>
                      <it.icon className="size-4" />{it.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { me, loading, logout } = useSession();
  const [open, setOpen] = useState(false);
  const path = usePathname();
  const router = useRouter();
  const enrolling = !!me?.mfa.enrollment_required;
  // Company policy: users without 2FA may only reach the account page until they enrol.
  useEffect(() => {
    if (enrolling && path !== "/app/account") router.replace("/app/account?setup=1");
  }, [enrolling, path, router]);

  return (
    <div className="flex min-h-dvh">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col border-r bg-surface lg:flex">
        <div className="flex h-14 items-center border-b px-4"><Link href="/app"><Logo /></Link></div>
        <div className="flex-1 overflow-y-auto px-3 py-4">{loading || enrolling ? <NavSkeleton /> : <Nav />}</div>
        <CompanyCard />
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-950/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-surface shadow-xl">
            <div className="flex h-14 items-center justify-between border-b px-4">
              <Logo /><button onClick={() => setOpen(false)} aria-label="Close menu"><X className="size-5" /></button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-4"><Nav onNavigate={() => setOpen(false)} /></div>
            <CompanyCard />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur sm:px-6">
          <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="size-5" /></button>
          {me?.company.is_demo && (
            <span className="hidden rounded-md bg-warning-soft px-2 py-1 text-xs font-medium text-warning sm:inline">Demo workspace · synthetic data</span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            {me && (
              <Link href="/app/account" className="hidden rounded-lg px-2 py-1 text-right hover:bg-surface-muted sm:block" title="Account & security">
                <p className="text-sm font-medium leading-tight" data-testid="current-user">{me.user.full_name}</p>
                <p className="text-xs text-muted-foreground">{humanize(me.user.role)}{me.mfa.enabled ? " · 2FA on" : ""}</p>
              </Link>
            )}
            <Button variant="ghost" size="icon" onClick={() => void logout()} aria-label="Sign out" title="Sign out"><LogOut /></Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:py-8">{children}</main>
      </div>
    </div>
  );
}

function CompanyCard() {
  const { me } = useSession();
  if (!me) return null;
  return (
    <div className="border-t p-3">
      <div className="flex items-center gap-2 rounded-lg bg-surface-muted px-3 py-2">
        <Building2 className="size-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">{me.company.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">{me.company.gstin ?? "GSTIN not set"}</p>
        </div>
      </div>
    </div>
  );
}

function NavSkeleton() {
  return <div className="space-y-2">{Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} className="h-8" />)}</div>;
}
