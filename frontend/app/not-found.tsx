import Link from "next/link";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 px-4 text-center">
      <Logo />
      <div><p className="num text-5xl font-semibold text-primary">404</p><h1 className="mt-2 text-lg font-semibold">Page not found</h1>
        <p className="mt-1 text-sm text-muted-foreground">The page may have moved, or you may not have access to it.</p></div>
      <div className="flex gap-2"><Button variant="outline" asChild><Link href="/">Home</Link></Button><Button asChild><Link href="/app">Go to workspace</Link></Button></div>
    </div>
  );
}
