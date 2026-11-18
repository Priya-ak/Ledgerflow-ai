"use client";

import { ShieldOff } from "lucide-react";
import { EmptyState, Skeleton } from "@/components/ui/feedback";
import { useSession } from "@/lib/session";

/** UX guard for pages; the backend independently enforces the same permission. */
export function RequirePermission({ perm, children }: { perm: string; children: React.ReactNode }) {
  const { me, loading, can } = useSession();
  if (loading || !me) return <Skeleton className="h-40" />;
  if (!can(perm)) return <EmptyState icon={ShieldOff} title="You don't have access to this page" description="Ask an administrator if you need this permission." />;
  return <>{children}</>;
}
