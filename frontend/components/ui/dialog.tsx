"use client";

import * as D from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Dialog = D.Root;
export const DialogTrigger = D.Trigger;
export const DialogClose = D.Close;

export function DialogContent({ className, children, title, description, wide }: { className?: string; children: React.ReactNode; title: string; description?: string; wide?: boolean }) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-[2px]" />
      <D.Content
        className={cn("fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border bg-surface p-6 shadow-xl", wide ? "max-w-3xl" : "max-w-lg", className)}
      >
        <div className="mb-4 pr-8">
          <D.Title className="text-base font-semibold">{title}</D.Title>
          {description ? <D.Description className="mt-1 text-sm text-muted-foreground">{description}</D.Description> : <D.Description className="sr-only">{title}</D.Description>}
        </div>
        {children}
        <D.Close className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:bg-surface-muted" aria-label="Close">
          <X className="size-4" />
        </D.Close>
      </D.Content>
    </D.Portal>
  );
}
