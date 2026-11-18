"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { api, errorMessage, json } from "@/lib/api";

const schema = z.object({ email: z.string().email("Enter a valid email") });

export default function ForgotPasswordPage() {
  const [result, setResult] = useState<{ message: string; dev_reset_token: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<{ email: string }>({ resolver: zodResolver(schema) });
  const onSubmit = async (v: { email: string }) => {
    setError(null);
    try { setResult(await api("/auth/forgot-password", { method: "POST", body: json(v) })); } catch (e) { setError(errorMessage(e)); }
  };
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Reset your password</h1>
      <p className="mt-1 text-sm text-muted-foreground">Enter the email you sign in with.</p>
      {result ? (
        <div className="mt-6 space-y-4">
          <Callout tone="success">{result.message}</Callout>
          {result.dev_reset_token ? (
            <Callout tone="warning" title="Development mode">
              Email delivery is not configured, so the reset link is shown here (never in production).{" "}
              <Link className="font-medium underline" href={`/reset-password?token=${encodeURIComponent(result.dev_reset_token)}`}>Set a new password</Link>
            </Callout>
          ) : (
            <p className="text-sm text-muted-foreground">If email delivery is configured for this workspace you will receive a link shortly. Otherwise, ask your administrator to reset your access.</p>
          )}
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
          {error && <Callout tone="danger">{error}</Callout>}
          <Field label="Email" htmlFor="email" error={errors.email?.message}><Input id="email" type="email" {...register("email")} /></Field>
          <Button type="submit" className="w-full" loading={isSubmitting}>Send reset instructions</Button>
        </form>
      )}
      <p className="mt-6 text-center text-sm"><Link href="/login" className="text-primary hover:underline">Back to sign in</Link></p>
    </div>
  );
}
