import { useEffect, useState } from 'react';

export type ShoveRange = {
  id: string;
  label: string;
  category: string;
  events: number;
  grid: {
    rows: string[];
    cols: string[];
    values: number[][];
  };
  summary_primary: { group: string; percent: number }[];
  summary_secondary: { group: string; percent: number }[];
  summary_events: number;
};

export type ShoveEquity = {
  id: string;
  label: string;
  equity_grid: {
    rows: string[];
    cols: string[];
    values: number[][];
  };
  ev_grid: {
    rows: string[];
    cols: string[];
    values: number[][];
  };
  metadata: Record<string, unknown>;
};

export type PreflopShoveData = {
  loading: boolean;
  error?: string;
  ranges: ShoveRange[];
  equity: ShoveEquity[];
};

const fetchJson = async <T,>(url: string): Promise<T> => {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
};

export const usePreflopShoveData = (sourceKey: string | null): PreflopShoveData => {
  const [ranges, setRanges] = useState<ShoveRange[]>([]);
  const [equity, setEquity] = useState<ShoveEquity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(undefined);
      try {
        const baseRangesUrl = '/api/preflop/shove/ranges';
        const baseEquityUrl = '/api/preflop/shove/equity';
        const suffix =
          sourceKey && sourceKey.trim().length > 0
            ? `?source=${encodeURIComponent(sourceKey)}`
            : '';
        const [rangeData, equityData] = await Promise.all([
          fetchJson<ShoveRange[]>(`${baseRangesUrl}${suffix}`),
          fetchJson<ShoveEquity[]>(`${baseEquityUrl}${suffix}`),
        ]);
        if (!cancelled) {
          setRanges(rangeData);
          setEquity(equityData);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [sourceKey]);

  return { loading, error, ranges, equity };
};
