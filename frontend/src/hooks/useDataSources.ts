import { useEffect, useMemo, useState } from 'react';

export type DataSource = {
  key: string;
  label: string;
};

type RawPayload = {
  sources: DataSource[];
  active?: string | null;
};

type HookState = {
  sources: DataSource[];
  active: string | null;
  loading: boolean;
  error: string | null;
};

const initialState: HookState = {
  sources: [],
  active: null,
  loading: true,
  error: null,
};

export const useDataSources = () => {
  const [state, setState] = useState<HookState>(initialState);

  useEffect(() => {
    let active = true;

    const fetchData = async () => {
      try {
        const response = await fetch('/api/data-sources');
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload = (await response.json()) as RawPayload;
        if (!active) {
          return;
        }
        setState({
          sources: payload.sources ?? [],
          active: payload.active ?? null,
          loading: false,
          error: null,
        });
      } catch (err) {
        if (!active) {
          return;
        }
        setState({
          sources: [],
          active: null,
          loading: false,
          error: 'Failed to load data sources.',
        });
      }
    };

    fetchData();

    return () => {
      active = false;
    };
  }, []);

  return useMemo(() => state, [state]);
};

