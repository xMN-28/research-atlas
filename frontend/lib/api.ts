'use client';
import { useEffect, useState } from 'react';
export function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setData(null);
    fetch(`/api/${path}`, { signal: controller.signal }).then(async response => {
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(typeof payload.detail === 'string' ? payload.detail : `Request failed (${response.status}). Check that the local backend is running.`);
      }
      return response.json() as Promise<T>;
    }).then(setData).catch(error => { if (error.name !== 'AbortError') setError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, attempt]);
  return { data, error, loading, retry: () => setAttempt(n => n + 1) };
}
