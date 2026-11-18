"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Copy, Download, KeyRound, ShieldCheck, ShieldOff } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Callout, Skeleton } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page";
import { api, errorMessage, json } from "@/lib/api";
import { useSession } from "@/lib/session";
import { dateTime, humanize } from "@/lib/utils";

export default function AccountPage() {
  return <Suspense><Account /></Suspense>;
}

function Account() {
  const { me } = useSession();
  const setup = useSearchParams().get("setup") === "1";
  if (!me) return <Skeleton className="h-96" />;
  return (
    <>
      <PageHeader title="Account & security" description="Your profile, password and two-factor authentication." />
      {me.mfa.enrollment_required && (
        <Callout tone="warning" className="mb-6" title="Two-factor authentication is required">
          {me.company.name} requires two-factor authentication. Set it up below to continue using LedgerFlow.
        </Callout>
      )}
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {[["Name", me.user.full_name], ["Email", me.user.email], ["Role", humanize(me.user.role)], ["Company", me.company.name], ["Last sign-in", dateTime(me.user.last_login_at)]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b py-2 last:border-0"><span className="text-muted-foreground">{k}</span><span className="text-right font-medium">{v}</span></div>
            ))}
          </CardContent>
        </Card>
        <TwoFactorCard autoStart={setup || me.mfa.enrollment_required} />
        {!me.mfa.enrollment_required && <PasswordCard />}
      </div>
    </>
  );
}

const pwSchema = z.object({
  current_password: z.string().min(1, "Required"),
  new_password: z.string().min(10, "At least 10 characters").regex(/[A-Za-z]/, "Include a letter").regex(/\d/, "Include a digit").max(72),
  confirm: z.string(),
}).refine((v) => v.new_password === v.confirm, { message: "Passwords do not match", path: ["confirm"] });

function PasswordCard() {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<z.infer<typeof pwSchema>>({ resolver: zodResolver(pwSchema) });
  return (
    <Card>
      <CardHeader><div><CardTitle>Change password</CardTitle><CardDescription>Other devices are signed out. You&apos;ll get a confirmation email.</CardDescription></div></CardHeader>
      <CardContent>
        <form className="space-y-4" noValidate onSubmit={handleSubmit(async (v) => {
          try { await api("/auth/change-password", { method: "POST", body: json({ current_password: v.current_password, new_password: v.new_password }) }); toast.success("Password changed"); reset(); }
          catch (e) { toast.error(errorMessage(e)); }
        })}>
          <Field label="Current password" error={errors.current_password?.message}><Input type="password" autoComplete="current-password" {...register("current_password")} /></Field>
          <Field label="New password" error={errors.new_password?.message}><Input type="password" autoComplete="new-password" {...register("new_password")} /></Field>
          <Field label="Confirm new password" error={errors.confirm?.message}><Input type="password" autoComplete="new-password" {...register("confirm")} /></Field>
          <Button type="submit" loading={isSubmitting}>Update password</Button>
        </form>
      </CardContent>
    </Card>
  );
}

type Setup = { secret: string; otpauth_uri: string; qr_svg: string };

function TwoFactorCard({ autoStart }: { autoStart: boolean }) {
  const { me, refresh } = useSession();
  const [setup, setSetup] = useState<Setup | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"idle" | "disable" | "regen">("idle");
  const enabled = me!.mfa.enabled;

  const start = async () => {
    setBusy(true);
    try { setSetup(await api<Setup>("/auth/mfa/setup", { method: "POST" })); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); }
  };
  const run = async (fn: () => Promise<void>) => { setBusy(true); try { await fn(); } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(false); } };

  return (
    <Card className={autoStart && !enabled ? "ring-2 ring-warning/40" : ""}>
      <CardHeader>
        <div><CardTitle>Two-factor authentication</CardTitle><CardDescription>Use an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…).</CardDescription></div>
        {enabled ? <Badge tone="success"><ShieldCheck className="size-3" /> On</Badge> : <Badge tone="neutral"><ShieldOff className="size-3" /> Off</Badge>}
      </CardHeader>
      <CardContent className="space-y-4">
        {codes && <RecoveryCodes codes={codes} onDone={() => setCodes(null)} />}

        {!enabled && !setup && !codes && (
          <>
            <p className="text-sm text-muted-foreground">Protect your account with a 6-digit code from your phone in addition to your password.</p>
            <Button onClick={start} loading={busy} data-testid="mfa-start"><KeyRound /> Set up two-factor authentication</Button>
          </>
        )}

        {!enabled && setup && (
          <div className="space-y-4">
            <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
              <li>Scan this QR code with your authenticator app.</li>
              <li>Enter the 6-digit code it shows to confirm.</li>
            </ol>
            <div className="flex flex-wrap items-center gap-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img alt="Two-factor QR code" className="size-44 rounded-lg border bg-white p-1" src={`data:image/svg+xml;base64,${btoa(setup.qr_svg)}`} />
              <div className="min-w-0 text-xs text-muted-foreground">
                <p>Can&apos;t scan? Enter this key manually:</p>
                <p className="mt-1 break-all font-mono text-sm text-foreground" data-testid="mfa-secret">{setup.secret.match(/.{1,4}/g)?.join(" ")}</p>
              </div>
            </div>
            <Field label="6-digit code">
              <Input data-testid="mfa-setup-code" inputMode="numeric" maxLength={6} className="num w-40 text-center tracking-[0.3em]" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
            </Field>
            <Button loading={busy} disabled={code.length !== 6} data-testid="mfa-confirm" onClick={() => run(async () => {
              const r = await api<{ recovery_codes: string[] }>("/auth/mfa/enable", { method: "POST", body: json({ code }) });
              setCodes(r.recovery_codes); setSetup(null); setCode(""); toast.success("Two-factor authentication is on"); await refresh();
            })}>Confirm and turn on</Button>
          </div>
        )}

        {enabled && !codes && (
          <>
            <p className="text-sm text-muted-foreground">
              Recovery codes remaining: <span className="num font-medium text-foreground">{me!.mfa.recovery_codes_remaining}</span>
              {me!.mfa.required_by_policy && <> · Required by your company</>}
            </p>
            {mode === "idle" && (
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => setMode("regen")}>New recovery codes</Button>
                {!me!.mfa.required_by_policy && <Button variant="ghost" onClick={() => setMode("disable")}>Turn off</Button>}
              </div>
            )}
            {mode === "regen" && (
              <div className="space-y-3 rounded-lg border p-3">
                <Field label="Current code from your app"><Input inputMode="numeric" maxLength={6} className="num w-40" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></Field>
                <div className="flex gap-2"><Button variant="outline" onClick={() => { setMode("idle"); setCode(""); }}>Cancel</Button>
                  <Button loading={busy} disabled={code.length !== 6} onClick={() => run(async () => {
                    const r = await api<{ recovery_codes: string[] }>("/auth/mfa/recovery-codes", { method: "POST", body: json({ code }) });
                    setCodes(r.recovery_codes); setMode("idle"); setCode(""); await refresh();
                  })}>Generate</Button></div>
              </div>
            )}
            {mode === "disable" && (
              <div className="space-y-3 rounded-lg border p-3">
                <Field label="Password"><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
                <Field label="Code from your app or a recovery code"><Input maxLength={20} value={code} onChange={(e) => setCode(e.target.value)} /></Field>
                <div className="flex gap-2"><Button variant="outline" onClick={() => { setMode("idle"); setCode(""); setPassword(""); }}>Cancel</Button>
                  <Button variant="danger" loading={busy} disabled={!password || code.trim().length < 6} onClick={() => run(async () => {
                    await api("/auth/mfa/disable", { method: "POST", body: json({ password, code: code.trim() }) });
                    toast.success("Two-factor authentication turned off"); setMode("idle"); setCode(""); setPassword(""); await refresh();
                  })}>Turn off</Button></div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const text = codes.join("\n");
  const save = () => {
    const url = URL.createObjectURL(new Blob([`LedgerFlow AI recovery codes\n\n${text}\n`], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url; a.download = "ledgerflow-recovery-codes.txt"; a.click(); URL.revokeObjectURL(url);
  };
  return (
    <div className="space-y-3 rounded-lg border border-warning/40 bg-warning-soft p-4" data-testid="recovery-codes">
      <p className="text-sm font-medium">Save your recovery codes now</p>
      <p className="text-xs text-foreground/80">Each code works once if you lose your phone. They won&apos;t be shown again.</p>
      <div className="grid grid-cols-2 gap-1 font-mono text-sm">{codes.map((c) => <span key={c}>{c}</span>)}</div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => navigator.clipboard.writeText(text).then(() => toast.success("Copied"))}><Copy /> Copy</Button>
        <Button size="sm" variant="outline" onClick={save}><Download /> Download</Button>
        <Button size="sm" onClick={onDone}>I&apos;ve saved them</Button>
      </div>
    </div>
  );
}
