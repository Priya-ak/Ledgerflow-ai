"use client";

import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/feedback";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-lg py-16">
      <Callout tone="danger" title="Something went wrong on this page">
        <p>Your data is safe. Try again, or go back to the dashboard.</p>
        {error.digest && <p className="mt-1 font-mono text-xs">Reference: {error.digest}</p>}
      </Callout>
      <div className="mt-4 flex gap-2"><Button onClick={reset}>Try again</Button><Button variant="outline" onClick={() => (window.location.href = "/app")}>Dashboard</Button></div>
    </div>
  );
}
