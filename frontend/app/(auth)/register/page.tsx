"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { api, errorMessage, json } from "@/lib/api";

const schema = z.object({
  company_name: z.string().min(2, "Company name is required"),
  gstin: z.string().regex(/^$|^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/, "Enter a valid 15-character GSTIN or leave blank").optional(),
  full_name: z.string().min(2, "Your name is required"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(10, "At least 10 characters").regex(/[A-Za-z]/, "Include a letter").regex(/\d/, "Include a digit").max(72),
});
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) });
  const onSubmit = async (v: Values) => {
    setError(null);
    try {
      await api("/auth/register", { method: "POST", body: json({ ...v, gstin: v.gstin || null }) });
      router.replace("/app");
    } catch (e) {
      setError(errorMessage(e));
    }
  };
  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Create your workspace</h1>
      <p className="mt-1 text-sm text-muted-foreground">You will be the administrator of a new company workspace.</p>
      <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
        {error && <Callout tone="danger">{error}</Callout>}
        <Field label="Company name" htmlFor="company_name" error={errors.company_name?.message}><Input id="company_name" aria-invalid={!!errors.company_name} {...register("company_name")} /></Field>
        <Field label="Company GSTIN (optional)" htmlFor="gstin" error={errors.gstin?.message}><Input id="gstin" className="uppercase" maxLength={15} {...register("gstin", { setValueAs: (v: string) => v?.toUpperCase().trim() })} /></Field>
        <Field label="Your full name" htmlFor="full_name" error={errors.full_name?.message}><Input id="full_name" autoComplete="name" {...register("full_name")} /></Field>
        <Field label="Work email" htmlFor="email" error={errors.email?.message}><Input id="email" type="email" autoComplete="email" {...register("email")} /></Field>
        <Field label="Password" htmlFor="password" error={errors.password?.message} hint="10+ characters with letters and digits"><Input id="password" type="password" autoComplete="new-password" {...register("password")} /></Field>
        <Button type="submit" className="w-full" loading={isSubmitting}>Create workspace</Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">Already have an account? <Link href="/login" className="font-medium text-primary hover:underline">Sign in</Link></p>
    </div>
  );
}
