import { useEffect, useState } from 'react';

export type RawPerformanceMetrics = {
  hand_count: number;
  net_cents: number;
  net_bb: number;
  vpip_hands: number;
  pfr_hands: number;
  three_bet_hands: number;
  three_bet_opportunities: number;
  pot_bb_sum: number;
  pot_samples: number;
};

export type PerformanceMetrics = {
  hand_count: number;
  net_bb: number;
  net_dollars: number;
  bb_per_100: number;
  vpip_pct: number;
  pfr_pct: number;
  three_bet_pct: number;
  avg_pot_bb: number;
  raw: RawPerformanceMetrics;
};

export type PositionPerformance = {
  position: string;
  metrics: PerformanceMetrics;
};

export type OpponentCountPerformance = {
  opponent_count: number;
  overall: PerformanceMetrics;
  positions: PositionPerformance[];
};

export type TimelineEntry = {
  hand_index: number;
  net_bb: number;
  position: string;
};

export type OpponentPerformanceResponse = {
  buckets: OpponentCountPerformance[];
  timeline: TimelineEntry[];
};

type State = {
  loading: boolean;
  error?: string;
  data: OpponentPerformanceResponse | null;
};

const fetchJson = async <T,>(url: string): Promise<T> => {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
};

export const useOpponentCountPerformance = (): State => {
  const [state, setState] = useState<State>({ loading: true, data: null });

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const payload = await fetchJson<OpponentPerformanceResponse>(
          '/api/performance/opponent-count',
        );
        if (!cancelled) {
          const normalized = {
            buckets: payload.buckets.map((entry) => ({
              ...entry,
              positions: entry.positions.map((position) => ({
                position: position.position,
                metrics: position.metrics,
              })),
            })),
            timeline: payload.timeline,
          };
          setState({ loading: false, data: normalized });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            loading: false,
            data: null,
            error: error instanceof Error ? error.message : 'Unknown error',
          });
        }
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
};
