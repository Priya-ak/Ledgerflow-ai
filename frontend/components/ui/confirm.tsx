"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";

export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = "Confirm", tone = "danger", onConfirm }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description: string; confirmLabel?: string;
  tone?: "danger" | "default"; onConfirm: () => Promise<void> | void;
}) {
  const [busy, setBusy] = React.useState(false);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} description={description}>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant={tone === "danger" ? "danger" : "default"} loading={busy}
            onClick={async () => { setBusy(true); try { await onConfirm(); onOpenChange(false); } finally { setBusy(false); } }}>
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
