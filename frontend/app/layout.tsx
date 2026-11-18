import type { Metadata, Viewport } from "next";
import { Toaster } from "sonner";
import { themeScript } from "@/components/theme-toggle";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "LedgerFlow AI — Intelligent Invoice Processing", template: "%s · LedgerFlow AI" },
  description: "Upload invoices, extract data with OCR, validate GST and totals, match purchase orders and route approvals — with a full audit trail.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = { themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f6f7f9" }, { media: "(prefers-color-scheme: dark)", color: "#0b1220" }] };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh">
        {children}
        <Toaster position="top-right" richColors closeButton />
      </body>
    </html>
  );
}
