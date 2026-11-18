"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { api, errorMessage, json } from "@/lib/api";

const schema = z.object({
  new_password: z.string().min(10, "At least 10 characters").regex(/[A-Za-z]/, "Include a letter").regex(/\d/, "Include a digit").max(72),
  confirm: z.string(),
}).refine((v) => v.new_password === v.confirm, { message: "Passwords do not match", path: ["confirm"] });
type Values = z.infer<typeof schema>;

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) });
  if (!token) return <Callout tone="danger">This reset link is missing its token. Request a new one.</Callout>;
  if (done) return <Callout tone="success" title="Password updated">All sessions were signed out. <Link href="/login" className="underline">Sign in</Link></Callout>;
  return (
    <form className="space-y-4" noValidate onSubmit={handleSubmit(async (v) => {
      setError(null);
      try { await api("/auth/reset-password", { method: "POST", body: json({ token, new_password: v.new_password }) }); setDone(true); } catch (e) { setError(errorMessage(e)); }
    })}>
      {error && <Callout tone="danger">{error}</Callout>}
      <Field label="New password" htmlFor="np" error={errors.new_password?.message}><Input id="np" type="password" autoComplete="new-password" {...register("new_password")} /></Field>
      <Field label="Confirm password" htmlFor="cp" error={errors.confirm?.message}><Input id="cp" type="password" autoComplete="new-password" {...register("confirm")} /></Field>
      <Button type="submit" className="w-full" loading={isSubmitting}>Update password</Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Choose a new password</h1>
      <Suspense><ResetForm /></Suspense>
    </div>
  );
}
