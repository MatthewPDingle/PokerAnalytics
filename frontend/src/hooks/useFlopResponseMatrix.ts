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
  avgRatio: number;
  avgAddedFlopBb: number;
  avgAddedAllBb: number;
  avgShareAll: number;
  avgBreakevenPct: number;
};

export type FlopResponseScenario = {
  heroPosition: string;
  betType: string;
  position: 'IP' | 'OOP';
  playerCount: number;
  textureKey: string;
  preflopKey: string;
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
  textures: SelectOption[];
  preflop_categories: SelectOption[];
  scenarios: Array<{
    hero_position: string;
    bet_type: string;
    position: 'IP' | 'OOP';
    player_count: number;
    texture_key: string;
    preflop_key: string;
    metrics: Array<{
      bucket_key: string;
      bucket_label: string;
      events: number;
      fold_events: number;
      call_events: number;
      raise_events: number;
      avg_ratio?: number;
      avg_added_flop_bb?: number;
      avg_added_all_bb?: number;
      avg_share_all?: number;
      avg_breakeven_pct?: number;
    }>;
  }>;
};

const SAMPLE_BUCKET_ORDER: FlopBucketMeta[] = [
  { key: 'pct_0_25', label: '0-25%' },
  { key: 'pct_25_40', label: '25-40%' },
  { key: 'pct_40_60', label: '40-60%' },
  { key: 'pct_60_80', label: '60-80%' },
  { key: 'pct_80_100', label: '80-100%' },
  { key: 'pct_100_plus', label: '100%+' },
  { key: 'all_in', label: 'All-In' },
  { key: 'one_bb', label: '1 BB' },
];

const SAMPLE_SCENARIOS: FlopResponseScenario[] = [
  {
    heroPosition: 'BTN',
    betType: 'cbet',
    position: 'IP',
    playerCount: 2,
    textureKey: 'any',
    preflopKey: 'any',
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
            avgRatio: 0.5,
            avgAddedFlopBb: 3.0,
            avgAddedAllBb: 5.0,
            avgShareAll: 1.8,
            avgBreakevenPct: 33.3,
          };
        case 'pct_60_80':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 185,
            foldEvents: 70,
            callEvents: 85,
            raiseEvents: 30,
            avgRatio: 0.7,
            avgAddedFlopBb: 3.8,
            avgAddedAllBb: 6.2,
            avgShareAll: 2.0,
            avgBreakevenPct: 41.2,
          };
        case 'pct_80_100':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 160,
            foldEvents: 60,
            callEvents: 70,
            raiseEvents: 30,
            avgRatio: 0.9,
            avgAddedFlopBb: 4.5,
            avgAddedAllBb: 7.4,
            avgShareAll: 2.4,
            avgBreakevenPct: 47.4,
          };
        case 'pct_100_plus':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 150,
            foldEvents: 65,
            callEvents: 60,
            raiseEvents: 25,
            avgRatio: 1.6,
            avgAddedFlopBb: 6.2,
            avgAddedAllBb: 10.8,
            avgShareAll: 3.1,
            avgBreakevenPct: 61.5,
          };
        case 'all_in':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 25,
            foldEvents: 8,
            callEvents: 10,
            raiseEvents: 7,
            avgRatio: 3.5,
            avgAddedFlopBb: 7.0,
            avgAddedAllBb: 14.0,
            avgShareAll: 4.2,
            avgBreakevenPct: 77.8,
          };
        case 'one_bb':
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 48,
            foldEvents: 20,
            callEvents: 22,
            raiseEvents: 6,
            avgRatio: 0.05,
            avgAddedFlopBb: 0.8,
            avgAddedAllBb: 1.2,
            avgShareAll: 0.9,
            avgBreakevenPct: 4.8,
          };
        default:
          return {
            bucketKey: bucket.key,
            bucketLabel: bucket.label,
            events: 0,
            foldEvents: 0,
            callEvents: 0,
            raiseEvents: 0,
            avgRatio: 0,
            avgAddedFlopBb: 0,
            avgAddedAllBb: 0,
            avgShareAll: 0,
            avgBreakevenPct: 0,
          };
      }
    }),
  },
  {
    heroPosition: 'SB',
    betType: 'donk',
    position: 'OOP',
    playerCount: 3,
    textureKey: 'any',
    preflopKey: 'any',
    metrics: SAMPLE_BUCKET_ORDER.map((bucket) => {
      if (bucket.key === 'pct_25_40') {
        return {
          bucketKey: bucket.key,
          bucketLabel: bucket.label,
          events: 60,
          foldEvents: 18,
          callEvents: 32,
          raiseEvents: 10,
          avgRatio: 0.3,
          avgAddedFlopBb: 2.0,
          avgAddedAllBb: 4.5,
          avgShareAll: 1.5,
          avgBreakevenPct: 23.1,
        };
      }
      return {
        bucketKey: bucket.key,
        bucketLabel: bucket.label,
        events: 0,
        foldEvents: 0,
        callEvents: 0,
        raiseEvents: 0,
        avgRatio: 0,
        avgAddedFlopBb: 0,
        avgAddedAllBb: 0,
        avgShareAll: 0,
        avgBreakevenPct: 0,
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
  textures: SelectOption[];
  preflopOptions: SelectOption[];
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
  textures: [],
  preflopOptions: [],
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
    textureKey: scenario.texture_key,
    preflopKey: scenario.preflop_key,
    metrics: scenario.metrics.map((metric) => ({
      bucketKey: metric.bucket_key,
      bucketLabel: metric.bucket_label,
      events: metric.events,
      foldEvents: metric.fold_events,
      callEvents: metric.call_events,
      raiseEvents: metric.raise_events,
      avgRatio: metric.avg_ratio ?? 0,
      avgAddedFlopBb: metric.avg_added_flop_bb ?? 0,
      avgAddedAllBb: metric.avg_added_all_bb ?? 0,
      avgShareAll: metric.avg_share_all ?? 0,
      avgBreakevenPct: metric.avg_breakeven_pct ?? 0,
    })),
  }));

  return {
    data: scenarios,
    bucketOrder: payload.bucket_order,
    betTypes: payload.bet_types,
    positions: payload.positions,
    playerCounts: payload.player_counts,
    heroPositions: payload.hero_positions,
    textures:
      payload.textures ?? [
        { key: 'any', label: 'All Textures' },
        { key: 'rainbow', label: 'Rainbow Flops' },
      ],
    preflopOptions:
      payload.preflop_categories ?? [
        { key: 'any', label: 'All Preflop Pots' },
        { key: 'limped', label: 'Limped Pot (No Raise)' },
        { key: 'single_raise', label: 'Single-Raise Pot' },
        { key: 'three_bet_plus', label: '3-Bet+ Pot' },
      ],
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
  textures: [
    { key: 'any', label: 'All Textures' },
    { key: 'rainbow', label: 'Rainbow Flops' },
  ],
  preflopOptions: [
    { key: 'any', label: 'All Preflop Pots' },
    { key: 'limped', label: 'Limped Pot (No Raise)' },
    { key: 'single_raise', label: 'Single-Raise Pot' },
    { key: 'three_bet_plus', label: '3-Bet+ Pot' },
  ],
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
