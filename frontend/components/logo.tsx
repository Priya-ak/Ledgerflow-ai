import { cn } from "@/lib/utils";

/** LedgerFlow mark: a folded document whose ledger lines resolve into a check. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7", className)} aria-hidden>
      <rect x="1" y="1" width="30" height="30" rx="8" className="fill-primary" />
      <path d="M10 7.5h8.5l4 4V24a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1V8.5a1 1 0 0 1 1-1Z" fill="none" stroke="white" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M18.5 7.5v4h4" fill="none" stroke="white" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M12 14h7M12 17.2h4.2" stroke="white" strokeWidth="1.6" strokeLinecap="round" opacity="0.75" />
      <path d="m15.6 21 1.8 1.7 3.6-3.9" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <LogoMark />
      <span>LedgerFlow <span className="text-primary">AI</span></span>
    </span>
  );
}
