"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "@/lib/api";

/** Minimal data-fetching hook with loading / error / reload and stale-response protection. */
export function useFetch<T>(path: string | null, query?: Record<string, string | number | boolean | undefined | null>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const key = path ? `${path}?${JSON.stringify(query ?? {})}` : null;
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (!path) return;
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const res = await api<T>(path, { query: query ?? undefined });
      if (id === seq.current) setData(res);
    } catch (e) {
      if (id === seq.current) setError(errorMessage(e));
    } finally {
      if (id === seq.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, error, loading, reload: load, setData };
}
