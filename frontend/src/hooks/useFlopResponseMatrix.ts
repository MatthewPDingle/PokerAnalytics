import { useEffect, useMemo, useState } from 'react';

export type FlopBucketMeta = {
  key: string;
  label: string;
};

export type FlopResponseMetric = {
  bucketKey: string;
  bucketLabel: string;
  events: number;
  foldEvents: number;
  callEvents: number;
  raiseEvents: number;
};

export type FlopResponseScenario = {
  heroPosition: string;
  betType: string;
  position: 'IP' | 'OOP';
  playerCount: number;
  metrics: FlopResponseMetric[];
};

export type SelectOption = {
  key: string;
  label: string;
};

type RawPayload = {
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
      fold_events: number;
      call_events: number;
      raise_events: number;
    }>;
  }>;
};

const SAMPLE_BUCKET_ORDER: FlopBucketMeta[] = [
  { key: 'pct_0_25', label: '0-25%' },
  { key: 'pct_25_40', label: '25-40%' },
  { key: 'pct_40_60', label: '40-60%' },
  { key: 'pct_60_80', label: '60-80%' },
  { key: 'pct_80_100', label: '80-100%' },
  { key: 'pct_100_125', label: '100-125%' },
  { key: 'pct_125_200', label: '125-200%' },
  { key: 'pct_200_300', label: '200-300%' },
  { key: 'pct_300_plus', label: '300%+' },
  { key: 'all_in', label: 'All-In' },
  { key: 'one_bb', label: '1 BB' },
];

const SAMPLE_SCENARIOS: FlopResponseScenario[] = [
  {
    heroPosition: 'BTN',
    betType: 'cbet',
    position: 'IP',
    playerCount: 2,
    metrics: SAMPLE_BUCKET_ORDER.map((bucket) => {
      switch (bucket.key) {
        case 'pct_40_60':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 220,
            foldEvents: 110,
            callEvents: 80,
            raiseEvents: 30,
          };
        case 'pct_60_80':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 185,
            foldEvents: 70,
            callEvents: 85,
            raiseEvents: 30,
          };
        case 'pct_80_100':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 160,
            foldEvents: 60,
            callEvents: 70,
            raiseEvents: 30,
          };
        case 'pct_100_125':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 120,
            foldEvents: 45,
            callEvents: 55,
            raiseEvents: 20,
          };
        case 'pct_125_200':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 90,
            foldEvents: 35,
            callEvents: 45,
            raiseEvents: 10,
          };
        case 'all_in':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 25,
            foldEvents: 8,
            callEvents: 10,
            raiseEvents: 7,
          };
        case 'one_bb':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 48,
            foldEvents: 20,
            callEvents: 22,
            raiseEvents: 6,
          };
        default:
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 0,
            foldEvents: 0,
            callEvents: 0,
            raiseEvents: 0,
          };
      }
    }),
  },
  {
    heroPosition: 'SB',
    betType: 'donk',
    position: 'OOP',
    playerCount: 3,
    metrics: SAMPLE_BUCKET_ORDER.map((bucket) => {
      if (bucket.key === 'pct_25_40') {
        return {
          bucketKey: bucket.key,
          bucketLabel: bucket.label,
          events: 60,
          foldEvents: 18,
          callEvents: 32,
          raiseEvents: 10,
        };
      }
      return {
        bucketKey: bucket.key,
        bucketLabel: bucket.label,
        events: 0,
        foldEvents: 0,
        callEvents: 0,
        raiseEvents: 0,
      };
    }),
  },
];

const SAMPLE_OPTIONS: SelectOption[] = [
  { key: 'cbet', label: 'Continuation Bet' },
  { key: 'donk', label: 'Donk Bet' },
  { key: 'stab', label: 'Stab / Other' },
];

const SAMPLE_POSITIONS: SelectOption[] = [
  { key: 'IP', label: 'In Position' },
  { key: 'OOP', label: 'Out of Position' },
];

type HookState = {
  data: FlopResponseScenario[];
  bucketOrder: FlopBucketMeta[];
  betTypes: SelectOption[];
  positions: SelectOption[];
  playerCounts: number[];
  heroPositions: string[];
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const initialState: HookState = {
  data: [],
  bucketOrder: [],
  betTypes: [],
  positions: [],
  playerCounts: [],
  heroPositions: [],
  loading: true,
  error: null,
  usingSample: false,
};

const transformPayload = (payload: RawPayload): HookState => {
  const scenarios: FlopResponseScenario[] = payload.scenarios.map((scenario) => ({
    heroPosition: scenario.hero_position,
    betType: scenario.bet_type,
    position: scenario.position,
    playerCount: scenario.player_count,
    metrics: scenario.metrics.map((metric) => ({
      bucketKey: metric.bucket_key,
      bucketLabel: metric.bucket_label,
      events: metric.events,
      foldEvents: metric.fold_events,
      callEvents: metric.call_events,
      raiseEvents: metric.raise_events,
    })),
  }));

  return {
    data: scenarios,
    bucketOrder: payload.bucket_order,
    betTypes: payload.bet_types,
    positions: payload.positions,
    playerCounts: payload.player_counts,
     heroPositions: payload.hero_positions,
    loading: false,
    error: null,
    usingSample: false,
  };
};

const SAMPLE_STATE: HookState = {
  data: SAMPLE_SCENARIOS,
  bucketOrder: SAMPLE_BUCKET_ORDER,
  betTypes: SAMPLE_OPTIONS,
  positions: SAMPLE_POSITIONS,
  playerCounts: [2, 3],
  heroPositions: ['SB', 'BB', 'UTG', 'BTN'],
  loading: false,
  error: 'Using sample flop response data (API unavailable).',
  usingSample: true,
};

export const useFlopResponseMatrix = () => {
  const [state, setState] = useState<HookState>(initialState);

  useEffect(() => {
    let active = true;

    const fetchData = async () => {
      try {
        const response = await fetch('/api/flop/response-matrix');
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload = (await response.json()) as RawPayload;
        if (!active) {
          return;
        }
        setState(transformPayload(payload));
      } catch (err) {
        if (!active) {
          return;
        }
        // Fallback to sample data so the UI stays functional during development.
        setState(SAMPLE_STATE);
      }
    };

    fetchData();

    return () => {
      active = false;
    };
  }, []);

  return useMemo(() => state, [state]);
};
