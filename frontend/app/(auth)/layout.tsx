import Link from "next/link";
import { Logo } from "@/components/logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="flex flex-col px-4 py-8 sm:px-10">
        <Link href="/" aria-label="LedgerFlow AI home"><Logo /></Link>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-sm">{children}</div>
        </div>
      </div>
      <div className="hidden border-l bg-surface lg:flex lg:flex-col lg:justify-center lg:px-16">
        <blockquote className="max-w-md">
          <p className="text-2xl font-semibold leading-snug tracking-tight">“Every invoice checked to the paisa, every decision on record.”</p>
          <ul className="mt-8 space-y-3 text-sm text-muted-foreground">
            <li>• OCR and structured extraction for PDF, JPG and PNG</li>
            <li>• Exact-decimal GST validation and duplicate detection</li>
            <li>• Purchase-order matching and multi-level approvals</li>
            <li>• Append-only audit trail and Excel reporting</li>
          </ul>
        </blockquote>
      </div>
    </div>
  );
}
