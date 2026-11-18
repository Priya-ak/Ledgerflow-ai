/** Typed fetch wrapper. Uses the same-origin /api/v1 proxy with the httpOnly session cookie. */
export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  requestId?: string;
  constructor(status: number, code: string, message: string, details?: unknown, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function qs(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export async function api<T>(path: string, init: RequestInit & { query?: Query } = {}): Promise<T> {
  const { query, headers, ...rest } = init;
  const isForm = typeof FormData !== "undefined" && rest.body instanceof FormData;
  const res = await fetch(`/api/v1${path}${qs(query)}`, {
    credentials: "same-origin",
    ...rest,
    headers: { ...(isForm || !rest.body ? {} : { "Content-Type": "application/json" }), ...headers },
  });
  if (!res.ok) {
    let body: { error?: { code?: string; message?: string; details?: unknown; request_id?: string } } = {};
    try {
      body = await res.json();
    } catch {
      /* non-JSON error */
    }
    const e = body.error ?? {};
    if (typeof window !== "undefined" && window.location.pathname.startsWith("/app")) {
      if (res.status === 401) window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
      else if (e.code === "mfa_enrollment_required" && window.location.pathname !== "/app/account") window.location.href = "/app/account?setup=1";
    }
    throw new ApiError(res.status, e.code ?? "error", e.message ?? `Request failed (${res.status})`, e.details, e.request_id);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const json = (data: unknown) => JSON.stringify(data);

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === "validation_error" && Array.isArray(err.details) && err.details.length) {
      const d = err.details[0] as { loc?: string[]; msg?: string };
      return `${d.loc?.slice(1).join(".") || "Input"}: ${d.msg}`;
    }
    return err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong.";
}

/** Trigger a browser download for an authenticated file endpoint. */
export async function download(path: string, query?: Query) {
  const res = await fetch(`/api/v1${path}${qs(query)}`, { credentials: "same-origin" });
  if (!res.ok) throw new ApiError(res.status, "download_failed", "Download failed.");
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") ?? "";
  const name = /filename="?([^"]+)"?/.exec(cd)?.[1] ?? "download";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
