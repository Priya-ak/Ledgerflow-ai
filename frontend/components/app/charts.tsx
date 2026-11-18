"use client";

import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { money } from "@/lib/utils";

const C = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const axis = { stroke: "var(--muted-foreground)", fontSize: 11, tickLine: false, axisLine: false } as const;
const tooltipStyle = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12, color: "var(--foreground)" };

function monthLabel(m: string) {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleDateString("en-IN", { month: "short", year: "2-digit" });
}

export function MonthlyValueChart({ data }: { data: { month: string; value: string; approved_value: string; count: number }[] }) {
  const rows = data.map((d) => ({ month: monthLabel(d.month), Total: Number(d.value), Approved: Number(d.approved_value), count: d.count }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows} margin={{ left: 0, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} stroke="var(--border)" />
        <XAxis dataKey="month" {...axis} />
        <YAxis {...axis} width={64} tickFormatter={(v) => money(v, true)} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => money(v)} cursor={{ fill: "var(--surface-muted)" }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Total" fill={C[1]} radius={[4, 4, 0, 0]} maxBarSize={28} />
        <Bar dataKey="Approved" fill={C[0]} radius={[4, 4, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function HorizontalBars({ data, valueLabel, isMoney, height = 240 }: { data: { name: string; value: number }[]; valueLabel: string; isMoney?: boolean; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid horizontal={false} stroke="var(--border)" />
        <XAxis type="number" {...axis} tickFormatter={(v) => (isMoney ? money(v, true) : String(v))} allowDecimals={false} />
        <YAxis type="category" dataKey="name" {...axis} width={150} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [isMoney ? money(v) : v, valueLabel]} cursor={{ fill: "var(--surface-muted)" }} />
        <Bar dataKey="value" fill={C[0]} radius={[0, 4, 4, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ApprovalTrendChart({ data }: { data: { month: string; approved: number; rejected: number }[] }) {
  const rows = data.map((d) => ({ month: monthLabel(d.month), Approved: d.approved, Rejected: d.rejected }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows} margin={{ left: 0, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} stroke="var(--border)" />
        <XAxis dataKey="month" {...axis} />
        <YAxis {...axis} width={32} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--surface-muted)" }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Approved" stackId="a" fill={C[0]} maxBarSize={28} />
        <Bar dataKey="Rejected" stackId="a" fill={C[4]} radius={[4, 4, 0, 0]} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  );
}
