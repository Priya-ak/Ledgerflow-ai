"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, UserX } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { RequirePermission } from "@/components/app/guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api, errorMessage, json } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Page, Role, User } from "@/lib/types";
import { useFetch } from "@/lib/use-fetch";
import { dateTime } from "@/lib/utils";

const schema = z.object({
  full_name: z.string().trim().min(2, "Required"), email: z.string().email("Invalid email"),
  role: z.enum(["admin", "accountant", "approver"]),
  send_invite: z.boolean(),
  password: z.string().max(72).optional(),
}).superRefine((v, ctx) => {
  if (v.send_invite) return;
  const pw = v.password ?? "";
  if (pw.length < 10 || !/[A-Za-z]/.test(pw) || !/\d/.test(pw))
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["password"], message: "10+ characters with letters and digits" });
});
type Values = z.infer<typeof schema>;

export default function UsersPage() {
  const { me } = useSession();
  const { data, error, reload } = useFetch<Page<User>>("/users", { page_size: 100 });
  const [creating, setCreating] = useState(false);
  const [deactivate, setDeactivate] = useState<User | null>(null);
  const [resetMfa, setResetMfa] = useState<User | null>(null);
  const update = async (u: User, patch: Partial<User>) => {
    try { await api(`/users/${u.id}`, { method: "PUT", body: json(patch) }); toast.success("User updated — they will need to sign in again"); void reload(); }
    catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <RequirePermission perm="users:manage">
      <PageHeader title="Users" description="Roles control what each person can do. Changing a role signs that user out everywhere."
        actions={<Button onClick={() => setCreating(true)}><Plus /> Add user</Button>} />
      <Card>
        {error ? <ErrorState message={error} onRetry={reload} /> : !data ? <div className="p-4"><Skeleton className="h-40" /></div> : (
          <Table>
            <THead><tr><TH>Name</TH><TH>Email</TH><TH>Role</TH><TH>Status</TH><TH>2FA</TH><TH>Last sign-in</TH><TH /></tr></THead>
            <TBody>
              {data.items.map((u) => (
                <TR key={u.id}>
                  <TD className="font-medium">{u.full_name}{u.id === me?.user.id && <Badge className="ml-2">You</Badge>}</TD>
                  <TD className="text-muted-foreground">{u.email}</TD>
                  <TD>
                    <Select className="h-8 w-36" value={u.role} disabled={!u.is_active} aria-label={`Role for ${u.full_name}`} onChange={(e) => update(u, { role: e.target.value as Role })}>
                      <option value="admin">Admin</option><option value="accountant">Accountant</option><option value="approver">Approver</option>
                    </Select>
                  </TD>
                  <TD>{u.is_active ? <Badge tone="success">Active</Badge> : <Badge>Deactivated</Badge>}</TD>
                  <TD>{u.mfa_enabled ? <span className="inline-flex items-center gap-1"><Badge tone="success">On</Badge>
                    {u.id !== me?.user.id && <Button size="sm" variant="link" className="h-auto text-xs" onClick={() => setResetMfa(u)}>Reset</Button>}</span> : <Badge>Off</Badge>}</TD>
                  <TD className="num text-xs text-muted-foreground">{dateTime(u.last_login_at)}</TD>
                  <TD className="text-right">
                    {u.is_active ? <Button size="sm" variant="ghost" onClick={() => setDeactivate(u)} disabled={u.id === me?.user.id}><UserX /> Deactivate</Button>
                      : <Button size="sm" variant="outline" onClick={() => update(u, { is_active: true })}>Reactivate</Button>}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
      {creating && <CreateUser onClose={() => setCreating(false)} onDone={() => { setCreating(false); void reload(); }} />}
      <ConfirmDialog open={!!deactivate} onOpenChange={(o) => !o && setDeactivate(null)} title={`Deactivate ${deactivate?.full_name}?`} confirmLabel="Deactivate"
        description="They are signed out immediately and cannot sign in. Their history stays in the audit log." onConfirm={() => update(deactivate!, { is_active: false })} />
      <ConfirmDialog open={!!resetMfa} onOpenChange={(o) => !o && setResetMfa(null)} title={`Reset two-factor for ${resetMfa?.full_name}?`} confirmLabel="Reset 2FA"
        description="Use this only if they lost their phone and recovery codes. They are signed out and must set up 2FA again; they receive a security email."
        onConfirm={async () => { try { await api(`/users/${resetMfa!.id}/mfa/reset`, { method: "POST" }); toast.success("Two-factor reset"); void reload(); } catch (e) { toast.error(errorMessage(e)); } }} />
    </RequirePermission>
  );
}

function CreateUser({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { role: "accountant", send_invite: true } });
  const invite = watch("send_invite");
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title="Add user" description="Invite by email so they choose their own password, or set an initial password yourself.">
        <form className="space-y-4" noValidate onSubmit={handleSubmit(async (v) => {
          try {
            await api("/users", { method: "POST", body: json({ ...v, password: v.send_invite ? null : v.password }) });
            toast.success(v.send_invite ? `Invitation emailed to ${v.email}` : "User created"); onDone();
          } catch (e) { toast.error(errorMessage(e)); }
        })}>
          <Field label="Full name" error={errors.full_name?.message}><Input {...register("full_name")} /></Field>
          <Field label="Email" error={errors.email?.message}><Input type="email" {...register("email")} /></Field>
          <Field label="Role"><Select {...register("role")}><option value="accountant">Accountant</option><option value="approver">Approver</option><option value="admin">Admin</option></Select></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" {...register("send_invite")} /> Email an invitation link (expires in 72 hours)</label>
          {!invite && <Field label="Initial password" error={errors.password?.message}><Input type="password" autoComplete="new-password" {...register("password")} /></Field>}
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" loading={isSubmitting}>Create user</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
