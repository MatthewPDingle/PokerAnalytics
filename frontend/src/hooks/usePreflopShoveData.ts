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

export const usePreflopShoveData = (): PreflopShoveData => {
  const [ranges, setRanges] = useState<ShoveRange[]>([]);
  const [equity, setEquity] = useState<ShoveEquity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [rangeData, equityData] = await Promise.all([
          fetchJson<ShoveRange[]>('/api/preflop/shove/ranges'),
          fetchJson<ShoveEquity[]>('/api/preflop/shove/equity'),
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
  }, []);

  return { loading, error, ranges, equity };
};
