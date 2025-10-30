import { useEffect, useMemo, useState } from 'react';

export type HandBucketMeta = {
  key: string;
  label: string;
};

export type HandMetric = {
  bucketKey: string;
  bucketLabel: string;
  events: number;
  categories: Record<string, number>;
};

export type HandScenario = {
  heroPosition: string;
  betType: string;
  position: 'IP' | 'OOP';
  playerCount: number;
  metrics: HandMetric[];
};

export type HandTypeMeta = {
  key: string;
  label: string;
  kind: 'primary' | 'draw';
};

export type HandGrouping = {
  key: string;
  label: string;
  members: string[];
};

type RawPayload = {
  bucket_order: HandBucketMeta[];
  hand_types: HandTypeMeta[];
  groupings: Array<{
    key: string;
    label: string;
    groups: Array<{ key: string; label: string; members: string[] }>;
  }>;
  bet_types: Array<{ key: string; label: string }>;
  positions: Array<{ key: string; label: string }>;
  hero_positions: string[];
  player_counts: number[];
  scenarios: Array<{
    hero_position: string;
    bet_type: string;
    position: 'IP' | 'OOP';
    player_count: number;
    metrics: Array<{
      bucket_key: string;
      bucket_label: string;
      events: number;
      categories: Record<string, number>;
    }>;
  }>;
};

type HandMatrixState = {
  data: HandScenario[];
  bucketOrder: HandBucketMeta[];
  handTypes: HandTypeMeta[];
  groupings: HandGrouping[];
  betTypes: Array<{ key: string; label: string }>;
  positions: Array<{ key: string; label: string }>;
  heroPositions: string[];
  playerCounts: number[];
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const SAMPLE_BUCKETS: HandBucketMeta[] = [
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

const SAMPLE_HAND_TYPES: HandTypeMeta[] = [
  { key: 'Air', label: 'Air', kind: 'primary' },
  { key: 'Underpair', label: 'Underpair', kind: 'primary' },
  { key: 'Bottom Pair', label: 'Bottom Pair', kind: 'primary' },
  { key: 'Middle Pair', label: 'Middle Pair', kind: 'primary' },
  { key: 'Top Pair', label: 'Top Pair', kind: 'primary' },
  { key: 'Overpair', label: 'Overpair', kind: 'primary' },
  { key: 'Two Pair', label: 'Two Pair', kind: 'primary' },
  { key: 'Trips/Set', label: 'Trips/Set', kind: 'primary' },
  { key: 'Straight', label: 'Straight', kind: 'primary' },
  { key: 'Flush', label: 'Flush', kind: 'primary' },
  { key: 'Full House', label: 'Full House', kind: 'primary' },
  { key: 'Quads', label: 'Quads', kind: 'primary' },
  { key: 'Flush Draw', label: 'Flush Draw', kind: 'draw' },
  { key: 'OESD/DG', label: 'OESD/DG', kind: 'draw' },
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

const SAMPLE_SCENARIOS: HandScenario[] = [
  {
    heroPosition: 'BTN',
    betType: 'cbet',
    position: 'IP',
    playerCount: 2,
    metrics: SAMPLE_BUCKETS.map((bucket, index) => {
      if (bucket.key === 'pct_40_60') {
        return {
          bucketKey: bucket.key,
          bucketLabel: bucket.label,
          events: 200,
          categories: {
            Air: 80,
            'Underpair': 20,
            'Bottom Pair': 15,
            'Middle Pair': 18,
            'Top Pair': 35,
            Overpair: 12,
            'Two Pair': 6,
            'Trips/Set': 4,
            Straight: 2,
            Flush: 1,
            'Full House': 1,
            Quads: 0,
            'Flush Draw': 18,
            'OESD/DG': 14,
          },
        };
      }
      if (bucket.key === 'pct_125_plus') {
        return {
          bucketKey: bucket.key,
          bucketLabel: bucket.label,
          events: 15,
          categories: {
            Air: 4,
            'Underpair': 1,
            'Bottom Pair': 0,
            'Middle Pair': 0,
            'Top Pair': 3,
            Overpair: 2,
            'Two Pair': 2,
            'Trips/Set': 3,
            Straight: 1,
            Flush: 0,
            'Full House': 0,
            Quads: 0,
            'Flush Draw': 2,
            'OESD/DG': 1,
          },
        };
      }
      return {
        bucketKey: bucket.key,
        bucketLabel: bucket.label,
        events: index % 3 === 0 ? 40 : 20,
        categories: Object.fromEntries(SAMPLE_HAND_TYPES.map((type) => [type.key, 0])),
      };
    }),
  },
];

const SAMPLE_BET_TYPES = [
  { key: 'cbet', label: 'Continuation Bet' },
  { key: 'donk', label: 'Donk Bet' },
];

const SAMPLE_POSITIONS = [
  { key: 'IP', label: 'In Position' },
  { key: 'OOP', label: 'Out of Position' },
];

const EMPTY_COUNTS = Object.fromEntries(SAMPLE_HAND_TYPES.map((type) => [type.key, 0]));

const INITIAL_STATE: HandMatrixState = {
  data: [],
  bucketOrder: [],
  handTypes: [],
  groupings: [],
  betTypes: [],
  positions: [],
  heroPositions: [],
  playerCounts: [],
  loading: true,
  error: null,
  usingSample: false,
};

const transform = (payload: RawPayload): HandMatrixState => {
  const scenarios: HandScenario[] = payload.scenarios.map((scenario) => ({
    heroPosition: scenario.hero_position,
    betType: scenario.bet_type,
    position: scenario.position,
    playerCount: scenario.player_count,
    metrics: scenario.metrics.map((metric) => ({
      bucketKey: metric.bucket_key,
      bucketLabel: metric.bucket_label,
      events: metric.events,
      categories: metric.categories,
    })),
  }));

  const groupings: HandGrouping[] = payload.groupings.flatMap((grouping) =>
    grouping.groups.map((group) => ({ key: group.key, label: group.label, members: group.members })),
  );

  return {
    data: scenarios,
    bucketOrder: payload.bucket_order,
    handTypes: payload.hand_types,
    groupings,
    betTypes: payload.bet_types,
    positions: payload.positions,
    heroPositions: payload.hero_positions,
    playerCounts: payload.player_counts,
    loading: false,
    error: null,
    usingSample: false,
  };
};

export const useFlopHandMatrix = (): HandMatrixState => {
  const [state, setState] = useState<HandMatrixState>(INITIAL_STATE);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const response = await fetch('/api/flop/hand-types');
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload: RawPayload = await response.json();
        if (!cancelled) {
          setState(transform(payload));
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        console.error('Failed to load flop hand matrix', err);
        setState({
          data: SAMPLE_SCENARIOS,
          bucketOrder: SAMPLE_BUCKETS,
          handTypes: SAMPLE_HAND_TYPES,
          groupings: SAMPLE_GROUPINGS,
          betTypes: SAMPLE_BET_TYPES,
          positions: SAMPLE_POSITIONS,
          heroPositions: ['BTN'],
          playerCounts: [2],
          loading: false,
          error: 'Unable to load flop hand breakdown. Displaying sample data.',
          usingSample: true,
        });
      }
    };

    fetchData();
    return () => {
      cancelled = true;
    };
  }, []);

  return useMemo(() => state, [state]);
};

export const emptyHandCategoryCounts = () => ({ ...EMPTY_COUNTS });

export default useFlopHandMatrix;
