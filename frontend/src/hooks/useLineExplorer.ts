import { useEffect, useMemo, useState } from 'react';

export type LineBucketMeta = {
  key: string;
  label: string;
};

export type LineMetric = {
  bucketKey: string;
  bucketLabel: string;
  events: number;
  foldEvents: number;
  callEvents: number;
  raiseEvents: number;
  avgRatio: number;
  avgBetBb: number;
};

export type LineScenario = {
  lineKey: string;
  heroPosition: string;
  betType: string;
  position: 'IP' | 'OOP';
  playerCount: number;
  responseType: 'call' | 'raise';
  metrics: LineMetric[];
};

export type LineSelectOption = {
  key: string;
  label: string;
};

type RawPayload = {
  version: number;
  bucket_order: LineBucketMeta[];
  line_definitions: LineSelectOption[];
  bet_types: LineSelectOption[];
  positions: LineSelectOption[];
  hero_positions: string[];
  player_counts: number[];
  response_types: LineSelectOption[];
  scenarios: Array<{
    line_key: string;
    hero_position: string;
    bet_type: string;
    position: 'IP' | 'OOP';
    player_count: number;
    response_type: 'call' | 'raise';
    metrics: Array<{
      bucket_key: string;
      bucket_label: string;
      events: number;
      fold_events: number;
      call_events: number;
      raise_events: number;
      avg_ratio: number;
      avg_bet_bb: number;
    }>;
  }>;
};

type HookState = {
  data: LineScenario[];
  bucketOrder: LineBucketMeta[];
  lineDefinitions: LineSelectOption[];
  betTypes: LineSelectOption[];
  positions: LineSelectOption[];
  heroPositions: string[];
  playerCounts: number[];
  responseTypes: LineSelectOption[];
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const SAMPLE_BUCKETS: LineBucketMeta[] = [
  { key: 'pct_0_25', label: '0-25%' },
  { key: 'pct_25_40', label: '25-40%' },
  { key: 'pct_40_60', label: '40-60%' },
  { key: 'pct_60_80', label: '60-80%' },
  { key: 'pct_80_100', label: '80-100%' },
  { key: 'pct_100_125', label: '100-125%' },
  { key: 'pct_125_200', label: '125-200%' },
  { key: 'pct_200_300', label: '200-300%' },
  { key: 'pct_300_plus', label: '300%+' },
  { key: 'pct_125_plus', label: '125%+' },
  { key: 'all_in', label: 'All-In' },
  { key: 'one_bb', label: '1 BB' },
];

const SAMPLE_SCENARIOS: LineScenario[] = [
  {
    lineKey: 'xc_turn_b',
    heroPosition: 'BTN',
    betType: 'cbet',
    position: 'IP',
    playerCount: 2,
    responseType: 'call',
    metrics: SAMPLE_BUCKETS.map((bucket) => ({
      bucketKey: bucket.key,
      bucketLabel: bucket.label,
      events: bucket.key === 'pct_40_60' ? 40 : 0,
      foldEvents: bucket.key === 'pct_40_60' ? 20 : 0,
      callEvents: bucket.key === 'pct_40_60' ? 18 : 0,
      raiseEvents: bucket.key === 'pct_40_60' ? 2 : 0,
      avgRatio: bucket.key === 'pct_40_60' ? 0.55 : 0,
      avgBetBb: bucket.key === 'pct_40_60' ? 5.5 : 0,
    })),
  },
  {
    lineKey: 'c_turn_b',
    heroPosition: 'CO',
    betType: 'cbet',
    position: 'IP',
    playerCount: 3,
    responseType: 'call',
    metrics: SAMPLE_BUCKETS.map((bucket) => ({
      bucketKey: bucket.key,
      bucketLabel: bucket.label,
      events: bucket.key === 'pct_25_40' ? 24 : 0,
      foldEvents: bucket.key === 'pct_25_40' ? 10 : 0,
      callEvents: bucket.key === 'pct_25_40' ? 12 : 0,
      raiseEvents: bucket.key === 'pct_25_40' ? 2 : 0,
      avgRatio: bucket.key === 'pct_25_40' ? 0.35 : 0,
      avgBetBb: bucket.key === 'pct_25_40' ? 3.5 : 0,
    })),
  },
];

const SAMPLE_STATE: HookState = {
  data: SAMPLE_SCENARIOS,
  bucketOrder: SAMPLE_BUCKETS,
  lineDefinitions: [
    { key: 'xc_turn_b', label: 'Flop Check-Call → Turn Bet' },
    { key: 'c_turn_b', label: 'Flop Call → Turn Bet' },
  ],
  betTypes: [
    { key: 'cbet', label: 'Continuation Bet' },
    { key: 'donk', label: 'Donk Bet' },
  ],
  positions: [
    { key: 'IP', label: 'In Position' },
    { key: 'OOP', label: 'Out of Position' },
  ],
  heroPositions: ['SB', 'BB', 'BTN'],
  playerCounts: [2],
  responseTypes: [
    { key: 'call', label: 'Call' },
    { key: 'raise', label: 'Raise' },
  ],
  loading: false,
  error: 'Using sample line explorer data (API unavailable).',
  usingSample: true,
};

const INITIAL_STATE: HookState = {
  data: [],
  bucketOrder: [],
  lineDefinitions: [],
  betTypes: [],
  positions: [],
  heroPositions: [],
  playerCounts: [],
  responseTypes: [],
  loading: true,
  error: null,
  usingSample: false,
};

const transformPayload = (payload: RawPayload): HookState => ({
  data: payload.scenarios.map((scenario) => ({
    lineKey: scenario.line_key,
    heroPosition: scenario.hero_position,
    betType: scenario.bet_type,
    position: scenario.position,
    playerCount: scenario.player_count,
    responseType: scenario.response_type,
    metrics: scenario.metrics.map((metric) => ({
      bucketKey: metric.bucket_key,
      bucketLabel: metric.bucket_label,
      events: metric.events,
      foldEvents: metric.fold_events,
      callEvents: metric.call_events,
      raiseEvents: metric.raise_events,
      avgRatio: metric.avg_ratio,
      avgBetBb: metric.avg_bet_bb,
    })),
  })),
  bucketOrder: payload.bucket_order,
  lineDefinitions: payload.line_definitions,
  betTypes: payload.bet_types,
  positions: payload.positions,
  heroPositions: payload.hero_positions,
  playerCounts: payload.player_counts,
  responseTypes: payload.response_types,
  loading: false,
  error: null,
  usingSample: false,
});

export const useLineExplorer = () => {
  const [state, setState] = useState<HookState>(INITIAL_STATE);

  useEffect(() => {
    let active = true;

    const fetchData = async () => {
      try {
        const response = await fetch('/api/lines/explorer');
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload = (await response.json()) as RawPayload;
        if (!active) {
          return;
        }
        setState(transformPayload(payload));
      } catch (error) {
        if (!active) {
          return;
        }
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

export default useLineExplorer;
