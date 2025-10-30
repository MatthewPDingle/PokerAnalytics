import { useEffect, useMemo, useState } from 'react';

import { FlopBucketMeta, FlopResponseScenario, SelectOption } from './useFlopResponseMatrix';

export type PotMetric = {
  bucketKey: string;
  bucketLabel: string;
  events: number;
  avgAddedBb: number;
};

export type PotScenario = {
  heroPosition: string;
  betType: string;
  position: 'IP' | 'OOP';
  playerCount: number;
  metrics: PotMetric[];
};

type RawPayload = {
  version: number;
  bucket_order: FlopBucketMeta[];
  bet_types: SelectOption[];
  positions: SelectOption[];
  player_counts: number[];
  hero_positions: string[];
  scenarios: Array<{
    hero_position: string;
    bet_type: string;
    position: 'IP' | 'OOP';
    player_count: number;
    metrics: Array<{
      bucket_key: string;
      bucket_label: string;
      events: number;
      avg_added_bb: number;
    }>;
  }>;
};

type HookState = {
  data: PotScenario[];
  bucketOrder: FlopBucketMeta[];
  betTypes: SelectOption[];
  positions: SelectOption[];
  heroPositions: string[];
  playerCounts: number[];
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const SAMPLE_BUCKETS: FlopBucketMeta[] = [
  { key: 'pct_0_25', label: '0-25%' },
  { key: 'pct_25_40', label: '25-40%' },
  { key: 'pct_40_60', label: '40-60%' },
  { key: 'pct_60_80', label: '60-80%' },
  { key: 'pct_80_100', label: '80-100%' },
  { key: 'pct_100_125', label: '100-125%' },
  { key: 'pct_125_200', label: '125-200%' },
  { key: 'pct_125_plus', label: '125%+' },
  { key: 'all_in', label: 'All-In' },
  { key: 'one_bb', label: '1 BB' },
];

const SAMPLE_SCENARIOS: PotScenario[] = [
  {
    heroPosition: 'BTN',
    betType: 'cbet',
    position: 'IP',
    playerCount: 2,
    metrics: SAMPLE_BUCKETS.map((bucket, index) => ({
      bucketKey: bucket.key,
      bucketLabel: bucket.label,
      events: index % 3 === 0 ? 40 : 20,
      avgAddedBb: index % 3 === 0 ? 3.5 : 1.8,
    })),
  },
];

const SAMPLE_BET_TYPES: SelectOption[] = [
  { key: 'cbet', label: 'Continuation Bet' },
  { key: 'donk', label: 'Donk Bet' },
];

const SAMPLE_POSITIONS: SelectOption[] = [
  { key: 'IP', label: 'In Position' },
  { key: 'OOP', label: 'Out of Position' },
];

const INITIAL_STATE: HookState = {
  data: [],
  bucketOrder: [],
  betTypes: [],
  positions: [],
  heroPositions: [],
  playerCounts: [],
  loading: true,
  error: null,
  usingSample: false,
};

const transform = (payload: RawPayload): HookState => {
  const scenarios: PotScenario[] = payload.scenarios.map((scenario) => ({
    heroPosition: scenario.hero_position,
    betType: scenario.bet_type,
    position: scenario.position,
    playerCount: scenario.player_count,
    metrics: scenario.metrics.map((metric) => ({
      bucketKey: metric.bucket_key,
      bucketLabel: metric.bucket_label,
      events: metric.events,
      avgAddedBb: metric.avg_added_bb,
    })),
  }));

  return {
    data: scenarios,
    bucketOrder: payload.bucket_order,
    betTypes: payload.bet_types,
    positions: payload.positions,
    heroPositions: payload.hero_positions,
    playerCounts: payload.player_counts,
    loading: false,
    error: null,
    usingSample: false,
  };
};

const useFlopPotContribution = (): HookState => {
  const [state, setState] = useState<HookState>(INITIAL_STATE);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const response = await fetch('/api/flop/pot-contribution');
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload: RawPayload = await response.json();
        if (!cancelled) {
          setState(transform(payload));
        }
      } catch (error) {
        console.error('Failed to load flop pot contribution', error);
        if (!cancelled) {
          setState({
            data: SAMPLE_SCENARIOS,
            bucketOrder: SAMPLE_BUCKETS,
            betTypes: SAMPLE_BET_TYPES,
            positions: SAMPLE_POSITIONS,
            heroPositions: ['BTN'],
            playerCounts: [2],
            loading: false,
            error: 'Unable to load pot contribution data. Displaying sample values.',
            usingSample: true,
          });
        }
      }
    };

    fetchData();
    return () => {
      cancelled = true;
    };
  }, []);

  return useMemo(() => state, [state]);
};

export default useFlopPotContribution;
