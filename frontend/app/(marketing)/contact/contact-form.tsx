"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/input";

const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "hello@ledgerflow.example";

const schema = z.object({
  name: z.string().min(2, "Please enter your name"),
  email: z.string().email("Enter a valid email"),
  company: z.string().optional(),
  volume: z.string(),
  message: z.string().min(10, "Tell us a little more (10+ characters)").max(2000),
});
type Values = z.infer<typeof schema>;

export function ContactForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { volume: "under-500" } });
  const onSubmit = (v: Values) => {
    const body = `Name: ${v.name}\nEmail: ${v.email}\nCompany: ${v.company ?? ""}\nMonthly invoices: ${v.volume}\n\n${v.message}`;
    window.location.href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("LedgerFlow AI enquiry")}&body=${encodeURIComponent(body)}`;
  };
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 rounded-xl border bg-surface p-6" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" error={errors.name?.message} htmlFor="name"><Input id="name" aria-invalid={!!errors.name} {...register("name")} /></Field>
        <Field label="Work email" error={errors.email?.message} htmlFor="email"><Input id="email" type="email" aria-invalid={!!errors.email} {...register("email")} /></Field>
        <Field label="Company" htmlFor="company"><Input id="company" {...register("company")} /></Field>
        <Field label="Invoices per month" htmlFor="volume">
          <Select id="volume" {...register("volume")}>
            <option value="under-500">Under 500</option><option value="500-2000">500 – 2,000</option><option value="2000+">More than 2,000</option>
          </Select>
        </Field>
      </div>
      <Field label="Message" error={errors.message?.message} htmlFor="message"><Textarea id="message" rows={5} aria-invalid={!!errors.message} {...register("message")} /></Field>
      <Button type="submit">Compose email</Button>
    </form>
  );
}
