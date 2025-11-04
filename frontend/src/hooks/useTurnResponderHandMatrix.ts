import { useEffect, useMemo, useState } from 'react';

export type ResponderHandMetric = {
  bucketKey: string;
  bucketLabel: string;
  events: number;
  categories: Record<string, number>;
};

export type ResponderHandScenario = {
  heroPosition: string;
  betLine: string;
  position: 'IP' | 'OOP';
  playerCount: number;
  responseType: 'call' | 'raise';
  textureKey: string;
  preflopKey: string;
  metrics: ResponderHandMetric[];
};

export type HandGrouping = {
  key: string;
  label: string;
  members: string[];
};

type RawResponderPayload = {
  bucket_order: Array<{ key: string; label: string }>;
  hand_types: Array<{ key: string; label: string; kind: 'primary' | 'draw' }>;
  groupings: Array<{
    key: string;
    label: string;
    groups: Array<{ key: string; label: string; members: string[] }>;
  }>;
  betting_lines: Array<{ key: string; label: string }>;
  positions: Array<{ key: string; label: string }>;
  hero_positions: string[];
  player_counts: number[];
  response_types: Array<{ key: string; label: string }>;
  textures: Array<{ key: string; label: string }>;
  preflop_categories: Array<{ key: string; label: string }>;
  scenarios: Array<{
    hero_position: string;
    bet_line: string;
    position: 'IP' | 'OOP';
    player_count: number;
    response_type: 'call' | 'raise';
    texture_key: string;
    preflop_key: string;
    metrics: Array<{
      bucket_key: string;
      bucket_label: string;
      events: number;
      categories: Record<string, number>;
    }>;
  }>;
};

type ResponderMatrixState = {
  data: ResponderHandScenario[];
  bucketOrder: Array<{ key: string; label: string }>;
  handTypes: Array<{ key: string; label: string; kind: 'primary' | 'draw' }>;
  groupings: HandGrouping[];
  betLines: Array<{ key: string; label: string }>;
  positions: Array<{ key: string; label: string }>;
  heroPositions: string[];
  playerCounts: number[];
  responseTypes: Array<{ key: string; label: string }>;
  textures: Array<{ key: string; label: string }>;
  preflopOptions: Array<{ key: string; label: string }>;
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const SAMPLE_BUCKETS = [
  { key: 'pct_0_25', label: '0-25%' },
  { key: 'pct_25_40', label: '25-40%' },
  { key: 'pct_40_60', label: '40-60%' },
  { key: 'pct_60_80', label: '60-80%' },
  { key: 'pct_80_100', label: '80-100%' },
  { key: 'pct_100_plus', label: '100%+' },
  { key: 'all_in', label: 'All-In' },
  { key: 'one_bb', label: '1 BB' },
];

const SAMPLE_HAND_TYPES = [
  { key: 'Air', label: 'Air', kind: 'primary' as const },
  { key: 'Underpair', label: 'Underpair', kind: 'primary' as const },
  { key: 'Bottom Pair', label: 'Bottom Pair', kind: 'primary' as const },
  { key: 'Middle Pair', label: 'Middle Pair', kind: 'primary' as const },
  { key: 'Top Pair', label: 'Top Pair', kind: 'primary' as const },
  { key: 'Overpair', label: 'Overpair', kind: 'primary' as const },
  { key: 'Two Pair', label: 'Two Pair', kind: 'primary' as const },
  { key: 'Trips/Set', label: 'Trips/Set', kind: 'primary' as const },
  { key: 'Straight', label: 'Straight', kind: 'primary' as const },
  { key: 'Flush', label: 'Flush', kind: 'primary' as const },
  { key: 'Full House', label: 'Full House', kind: 'primary' as const },
  { key: 'Quads', label: 'Quads', kind: 'primary' as const },
  { key: 'Flush Draw', label: 'Flush Draw', kind: 'draw' as const },
  { key: 'OESD/DG', label: 'OESD/DG', kind: 'draw' as const },
];

const SAMPLE_GROUPINGS: HandGrouping[] = [
  { key: 'Air', label: 'Air', members: ['Air'] },
  { key: 'Weak Pair', label: 'Weak Pair', members: ['Underpair', 'Bottom Pair', 'Middle Pair'] },
  { key: 'Top Pair', label: 'Top Pair', members: ['Top Pair'] },
  { key: 'Overpair', label: 'Overpair', members: ['Overpair'] },
  { key: 'Two Pair', label: 'Two Pair', members: ['Two Pair'] },
  { key: 'Trips/Set', label: 'Trips/Set', members: ['Trips/Set'] },
  { key: 'Monster', label: 'Monster', members: ['Straight', 'Flush', 'Full House', 'Quads'] },
  { key: 'Draw', label: 'Draw', members: ['Flush Draw', 'OESD/DG'] },
];

const EMPTY_CATEGORY_COUNTS = Object.fromEntries(SAMPLE_HAND_TYPES.map((type) => [type.key, 0]));

const SAMPLE_SCENARIOS: ResponderHandScenario[] = [
  {
    heroPosition: 'BTN',
    betLine: 'ip_float_stab',
    position: 'IP',
    playerCount: 2,
    responseType: 'call',
    textureKey: 'any',
    preflopKey: 'any',
    metrics: SAMPLE_BUCKETS.map((bucket) => ({
      bucketKey: bucket.key,
      bucketLabel: bucket.label,
      events: bucket.key === 'pct_40_60' ? 60 : 20,
      categories: {
        ...EMPTY_CATEGORY_COUNTS,
        Air: bucket.key === 'pct_40_60' ? 10 : 4,
        'Top Pair': bucket.key === 'pct_40_60' ? 18 : 6,
        'Overpair': bucket.key === 'pct_40_60' ? 8 : 4,
        'Trips/Set': bucket.key === 'pct_40_60' ? 4 : 1,
        'Flush Draw': bucket.key === 'pct_40_60' ? 9 : 2,
        'OESD/DG': bucket.key === 'pct_40_60' ? 6 : 1,
      },
    })),
  },
  {
    heroPosition: 'BTN',
    betLine: 'double_barrel',
    position: 'IP',
    playerCount: 2,
    responseType: 'raise',
    textureKey: 'any',
    preflopKey: 'any',
    metrics: SAMPLE_BUCKETS.map((bucket) => ({
      bucketKey: bucket.key,
      bucketLabel: bucket.label,
      events: bucket.key === 'pct_40_60' ? 12 : 4,
      categories: {
        ...EMPTY_CATEGORY_COUNTS,
        Air: bucket.key === 'pct_40_60' ? 1 : 0,
        'Top Pair': bucket.key === 'pct_40_60' ? 3 : 1,
        'Trips/Set': bucket.key === 'pct_40_60' ? 3 : 1,
        'Straight': bucket.key === 'pct_40_60' ? 2 : 0,
        'Flush Draw': bucket.key === 'pct_40_60' ? 3 : 1,
        'OESD/DG': bucket.key === 'pct_40_60' ? 2 : 1,
      },
    })),
  },
];

const SAMPLE_RESPONSE_TYPES = [
  { key: 'call', label: 'Call' },
  { key: 'raise', label: 'Raise' },
];

const INITIAL_STATE: ResponderMatrixState = {
  data: [],
  bucketOrder: [],
  handTypes: [],
  groupings: [],
  betLines: [],
  positions: [],
  heroPositions: [],
  playerCounts: [],
  responseTypes: [],
  textures: [],
  preflopOptions: [],
  loading: true,
  error: null,
  usingSample: false,
};

const SAMPLE_STATE: ResponderMatrixState = {
  data: SAMPLE_SCENARIOS,
  bucketOrder: SAMPLE_BUCKETS,
  handTypes: SAMPLE_HAND_TYPES,
  groupings: SAMPLE_GROUPINGS,
  betLines: [
    { key: 'double_barrel', label: 'Double Barrel (B;B)' },
    { key: 'ip_float_stab', label: 'IP Float Stab (C;X-B)' },
    { key: 'oop_xc_donk_lead', label: 'OOP XC Donk Lead (X-C;B)' },
  ],
  positions: [
    { key: 'IP', label: 'In Position' },
    { key: 'OOP', label: 'Out of Position' },
  ],
  heroPositions: ['SB', 'BB', 'UTG', 'BTN'],
  playerCounts: [2, 3],
  responseTypes: SAMPLE_RESPONSE_TYPES,
  textures: [
    { key: 'any', label: 'All Textures' },
    { key: 'rainbow', label: 'Rainbow Turns' },
  ],
  preflopOptions: [
    { key: 'any', label: 'All Preflop Pots' },
    { key: 'limped', label: 'Limped Pot (No Raise)' },
    { key: 'single_raise', label: 'Single-Raise Pot' },
    { key: 'three_bet_plus', label: '3-Bet+ Pot' },
  ],
  loading: false,
  error: 'Using sample responder hand matrix data (API unavailable).',
  usingSample: true,
};

const transformPayload = (payload: RawResponderPayload): ResponderMatrixState => ({
  data: payload.scenarios.map((scenario) => ({
    heroPosition: scenario.hero_position,
    betLine: scenario.bet_line,
    position: scenario.position,
    playerCount: scenario.player_count,
    responseType: scenario.response_type,
    textureKey: scenario.texture_key,
    preflopKey: scenario.preflop_key,
    metrics: scenario.metrics.map((metric) => ({
      bucketKey: metric.bucket_key,
      bucketLabel: metric.bucket_label,
      events: metric.events,
      categories: metric.categories,
    })),
  })),
  bucketOrder: payload.bucket_order,
  handTypes: payload.hand_types,
  groupings:
    payload.groupings.flatMap((grouping) =>
      grouping.groups.map((group) => ({ key: group.key, label: group.label, members: group.members })),
    ) || SAMPLE_GROUPINGS,
  betLines: payload.betting_lines,
  positions: payload.positions,
  heroPositions: payload.hero_positions,
  playerCounts: payload.player_counts,
  responseTypes: payload.response_types,
  textures:
    payload.textures ?? [
      { key: 'any', label: 'All Textures' },
      { key: 'rainbow', label: 'Rainbow Turns' },
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
});

export const useTurnResponderHandMatrix = () => {
  const [state, setState] = useState<ResponderMatrixState>(INITIAL_STATE);

  useEffect(() => {
    let active = true;

    const fetchData = async () => {
      try {
        const response = await fetch('/api/turn/responder-hand-matrix');
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload = (await response.json()) as RawResponderPayload;
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

export default useTurnResponderHandMatrix;
