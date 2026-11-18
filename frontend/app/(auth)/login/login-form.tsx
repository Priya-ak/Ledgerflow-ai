"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Briefcase, Calculator, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { api, errorMessage, json } from "@/lib/api";

const schema = z.object({ email: z.string().email("Enter a valid email"), password: z.string().min(1, "Enter your password") });
type Values = z.infer<typeof schema>;

// Demo accounts exist only in the seeded, clearly-labelled demo workspace (see README).
const DEMO_ENABLED = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";
const DEMO_PASSWORD = "LedgerFlow2026";
const DEMO = [
  { role: "Accountant", email: "accountant@ledgerflow-demo.example", icon: Calculator, hint: "Upload, review and submit" },
  { role: "Approver", email: "approver@ledgerflow-demo.example", icon: ShieldCheck, hint: "Approve or reject" },
  { role: "Admin", email: "admin@ledgerflow-demo.example", icon: Briefcase, hint: "Users, policy, audit" },
];

function safeNext(next: string | null) {
  return next && next.startsWith("/app") && !next.startsWith("//") ? next : "/app";
}

type LoginResult = { mfa_required?: boolean; mfa_token?: string; mfa?: { enrollment_required: boolean } };

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<string | null>(null);
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) });

  const finish = (r: LoginResult) => {
    router.replace(r.mfa?.enrollment_required ? "/app/account?setup=1" : safeNext(params.get("next")));
    router.refresh();
  };

  const onSubmit = async (v: Values) => {
    setError(null);
    try {
      const r = await api<LoginResult>("/auth/login", { method: "POST", body: json(v) });
      if (r.mfa_required && r.mfa_token) setChallenge(r.mfa_token);
      else finish(r);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  if (challenge) {
    return <MfaStep token={challenge} onDone={finish} onCancel={() => setChallenge(null)} />;
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-1 text-sm text-muted-foreground">Welcome back to LedgerFlow AI.</p>

      {DEMO_ENABLED && (
        <div className="mt-6 rounded-xl border bg-surface p-3">
          <p className="px-1 text-xs font-medium text-muted-foreground">Demo workspace · synthetic data · password {DEMO_PASSWORD}</p>
          <div className="mt-2 grid gap-1.5">
            {DEMO.map((d) => (
              <button key={d.email} type="button" data-testid={`demo-${d.role.toLowerCase()}`}
                onClick={() => { setValue("email", d.email); setValue("password", DEMO_PASSWORD); void handleSubmit(onSubmit)(); }}
                className="flex items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-surface-muted">
                <d.icon className="size-4 text-primary" />
                <span className="text-sm font-medium">{d.role}</span>
                <span className="ml-auto text-xs text-muted-foreground">{d.hint}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
        {error && <Callout tone="danger">{error}</Callout>}
        <Field label="Email" htmlFor="email" error={errors.email?.message}>
          <Input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email} {...register("email")} />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" aria-invalid={!!errors.password} {...register("password")} />
        </Field>
        <div className="flex justify-end"><Link href="/forgot-password" className="text-xs text-primary hover:underline">Forgot password?</Link></div>
        <Button type="submit" className="w-full" loading={isSubmitting}>Sign in</Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        New to LedgerFlow? <Link href="/register" className="font-medium text-primary hover:underline">Create a workspace</Link>
      </p>
    </div>
  );
}

function MfaStep({ token, onDone, onCancel }: { token: string; onDone: (r: LoginResult) => void; onCancel: () => void }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onDone(await api<LoginResult>("/auth/mfa/verify", { method: "POST", body: json({ mfa_token: token, code: code.trim() }) }));
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Two-factor verification</h1>
      <p className="mt-1 text-sm text-muted-foreground">Enter the 6-digit code from your authenticator app. Lost your phone? Use one of your recovery codes.</p>
      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        {error && <Callout tone="danger">{error}</Callout>}
        <Field label="Authentication code" htmlFor="mfa-code">
          <Input id="mfa-code" data-testid="mfa-code" autoFocus autoComplete="one-time-code" inputMode="text" maxLength={20}
            className="num text-center text-lg tracking-[0.3em]" value={code} onChange={(e) => setCode(e.target.value)} />
        </Field>
        <Button type="submit" className="w-full" loading={busy} disabled={code.trim().length < 6}>Verify and sign in</Button>
        <button type="button" className="w-full text-center text-xs text-muted-foreground hover:underline" onClick={onCancel}>Use a different account</button>
      </form>
    </div>
  );
}
