import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn, humanize } from "@/lib/utils";

const badge = cva("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap", {
  variants: {
    tone: {
      neutral: "bg-surface-muted text-muted-foreground ring-border",
      primary: "bg-primary-soft text-primary ring-primary/20",
      success: "bg-success-soft text-success ring-success/20",
      warning: "bg-warning-soft text-warning ring-warning/25",
      danger: "bg-danger-soft text-danger ring-danger/20",
      info: "bg-info-soft text-info ring-info/20",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export type Tone = NonNullable<VariantProps<typeof badge>["tone"]>;

export function Badge({ className, tone, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone }), className)} {...p} />;
}

const TONES: Record<string, Tone> = {
  approved: "success", passed: "success", matched: "success", processed: "success", active: "success", paid: "success", none: "neutral",
  pending_approval: "info", pending: "info", extracted: "primary", submitted: "info", open: "info", uploaded: "neutral",
  review_required: "warning", warnings: "warning", possible_duplicate: "warning", partially_matched: "warning", requires_review: "warning",
  partially_paid: "warning", processing: "info", draft: "neutral", not_run: "neutral", no_po_found: "neutral", archived: "neutral",
  rejected: "danger", failed: "danger", failed_processing: "danger", duplicate: "danger", mismatch: "danger", cancelled: "neutral",
  inactive: "neutral", unpaid: "neutral", resolved_not_duplicate: "success", closed: "neutral",
};

const LABELS: Record<string, string> = {
  pending_approval: "Pending approval", review_required: "Needs review", failed_processing: "Processing failed",
  possible_duplicate: "Possible duplicate", resolved_not_duplicate: "Not a duplicate", no_po_found: "No PO", not_run: "Not run",
  partially_matched: "Partial match", none: "No duplicate",
};

export function StatusBadge({ value, className }: { value: string | null | undefined; className?: string }) {
  if (!value) return <Badge className={className}>—</Badge>;
  return <Badge tone={TONES[value] ?? "neutral"} className={className}>{LABELS[value] ?? humanize(value)}</Badge>;
}
