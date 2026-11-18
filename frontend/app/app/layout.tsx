import type { Metadata } from "next";
import { AppShell } from "@/components/app/shell";
import { SessionProvider } from "@/lib/session";

export const metadata: Metadata = { title: "Workspace", robots: { index: false } };

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <AppShell>{children}</AppShell>
    </SessionProvider>
  );
}
