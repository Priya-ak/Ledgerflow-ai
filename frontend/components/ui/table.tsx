import * as React from "react";
import { cn } from "@/lib/utils";

export function Table({ className, ...p }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn("w-full caption-bottom text-sm", className)} {...p} />
    </div>
  );
}
export const THead = (p: React.HTMLAttributes<HTMLTableSectionElement>) => <thead className="bg-surface-muted/60" {...p} />;
export const TBody = (p: React.HTMLAttributes<HTMLTableSectionElement>) => <tbody className="divide-y" {...p} />;
export function TR({ className, ...p }: React.HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("transition-colors hover:bg-surface-muted/50", className)} {...p} />;
}
export function TH({ className, ...p }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={cn("h-9 px-4 text-left align-middle text-xs font-medium text-muted-foreground whitespace-nowrap border-b", className)} {...p} />;
}
export function TD({ className, ...p }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-4 py-2.5 align-middle", className)} {...p} />;
}
