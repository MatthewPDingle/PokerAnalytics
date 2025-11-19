import { useEffect, useMemo, useState } from 'react';

export type LineHandBucketMeta = {
  key: string;
  label: string;
};

export type LineHandMetric = {
  bucketKey: string;
  bucketLabel: string;
  events: number;
  categories: Record<string, number>;
};

export type LineHandScenario = {
  lineKey: string;
  heroPosition: string;
  betType: string;
  position: 'IP' | 'OOP';
  playerCount: number;
  responseType: 'call' | 'raise';
  metrics: LineHandMetric[];
};

export type LineHandGrouping = {
  key: string;
  label: string;
  members: string[];
};

type RawPayload = {
  version: number;
  bucket_order: LineHandBucketMeta[];
  hand_types: Array<{ key: string; label: string; kind: 'primary' | 'draw' }>;
  groupings: Array<{
    key: string;
    label: string;
    groups: Array<{ key: string; label: string; members: string[] }>;
  }>;
  bet_types: Array<{ key: string; label: string }>;
  positions: Array<{ key: string; label: string }>;
  hero_positions: string[];
  player_counts: number[];
  response_types: Array<{ key: string; label: string }>;
  line_definitions: Array<{ key: string; label: string }>;
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
      categories: Record<string, number>;
    }>;
  }>;
};

type HookState = {
  data: LineHandScenario[];
  bucketOrder: LineHandBucketMeta[];
  handTypes: Array<{ key: string; label: string; kind: 'primary' | 'draw' }>;
  groupings: LineHandGrouping[];
  betTypes: Array<{ key: string; label: string }>;
  positions: Array<{ key: string; label: string }>;
  heroPositions: string[];
  playerCounts: number[];
  responseTypes: Array<{ key: string; label: string }>;
  lineDefinitions: Array<{ key: string; label: string }>;
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const SAMPLE_STATE: HookState = {
  data: [
    {
      lineKey: 'xc_turn_b',
      heroPosition: 'BTN',
      betType: 'cbet',
      position: 'IP',
      playerCount: 2,
      responseType: 'call',
      metrics: [
        {
          bucketKey: 'pct_40_60',
          bucketLabel: '40-60%',
          events: 20,
          categories: {
            Air: 4,
            'Top Pair': 6,
            Overpair: 5,
            'Flush Draw': 3,
            'OESD/DG': 2,
          } as Record<string, number>,
        },
      ],
    },
  ],
  bucketOrder: [
    { key: 'pct_0_25', label: '0-25%' },
    { key: 'pct_25_40', label: '25-40%' },
    { key: 'pct_40_60', label: '40-60%' },
  ],
  handTypes: [
    { key: 'Air', label: 'Air', kind: 'primary' },
    { key: 'Top Pair', label: 'Top Pair', kind: 'primary' },
    { key: 'Overpair', label: 'Overpair', kind: 'primary' },
    { key: 'Flush Draw', label: 'Flush Draw', kind: 'draw' },
    { key: 'OESD/DG', label: 'OESD/DG', kind: 'draw' },
  ],
  groupings: [
    { key: 'Air', label: 'Air', members: ['Air'] },
    { key: 'Top Pair', label: 'Top Pair', members: ['Top Pair'] },
    { key: 'Overpair', label: 'Overpair', members: ['Overpair'] },
    { key: 'Draw', label: 'Draw', members: ['Flush Draw', 'OESD/DG'] },
  ],
  betTypes: [
    { key: 'cbet', label: 'Continuation Bet' },
  ],
  positions: [
    { key: 'IP', label: 'In Position' },
    { key: 'OOP', label: 'Out of Position' },
  ],
  heroPositions: ['SB', 'BTN'],
  playerCounts: [2],
  responseTypes: [
    { key: 'call', label: 'Call' },
    { key: 'raise', label: 'Raise' },
  ],
  lineDefinitions: [{ key: 'xc_turn_b', label: 'Flop Check-Call → Turn Bet' }],
  loading: false,
  error: 'Using sample line responder hand data (API unavailable).',
  usingSample: true,
};

const INITIAL_STATE: HookState = {
  data: [],
  bucketOrder: [],
  handTypes: [],
  groupings: [],
  betTypes: [],
  positions: [],
  heroPositions: [],
  playerCounts: [],
  responseTypes: [],
  lineDefinitions: [],
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
      categories: metric.categories,
    })),
  })),
  bucketOrder: payload.bucket_order,
  handTypes: payload.hand_types,
  groupings:
    payload.groupings.flatMap((grouping) =>
      grouping.groups.map((group) => ({ key: group.key, label: group.label, members: group.members })),
    ) || [],
  betTypes: payload.bet_types,
  positions: payload.positions,
  heroPositions: payload.hero_positions,
  playerCounts: payload.player_counts,
  responseTypes: payload.response_types,
  lineDefinitions: payload.line_definitions,
  loading: false,
  error: null,
  usingSample: false,
});

export const useLineResponderHandMatrix = (sourceKey: string | null) => {
  const [state, setState] = useState<HookState>(INITIAL_STATE);

  useEffect(() => {
    let active = true;

    setState((prev) => ({
      ...prev,
      loading: true,
      error: null,
      usingSample: false,
    }));

    const fetchData = async () => {
      try {
        const url =
          sourceKey && sourceKey.trim().length > 0
            ? `/api/lines/responder-hand-matrix?source=${encodeURIComponent(sourceKey)}`
            : '/api/lines/responder-hand-matrix';
        const response = await fetch(url);
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
  }, [sourceKey]);

  return useMemo(() => state, [state]);
};

export default useLineResponderHandMatrix;
