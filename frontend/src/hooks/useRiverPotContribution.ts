import { useEffect, useMemo, useState } from 'react';

import { RiverBucketMeta, SelectOption } from './useRiverResponseMatrix';

export type PotMetric = {
  bucketKey: string;
  bucketLabel: string;
  events: number;
  avgAddedBb: number;
};

export type PotScenario = {
  heroPosition: string;
  betLine: string;
  position: 'IP' | 'OOP';
  playerCount: number;
  textureKey: string;
  preflopKey: string;
  metrics: PotMetric[];
};

type RawPayload = {
  version: number;
  bucket_order: RiverBucketMeta[];
  betting_lines: SelectOption[];
  positions: SelectOption[];
  player_counts: number[];
  hero_positions: string[];
  textures: SelectOption[];
  preflop_categories: SelectOption[];
  scenarios: Array<{
    hero_position: string;
    bet_type: string;
    bet_line: string;
    position: 'IP' | 'OOP';
    player_count: number;
    texture_key: string;
    preflop_key: string;
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
  bucketOrder: RiverBucketMeta[];
  betLines: SelectOption[];
  positions: SelectOption[];
  heroPositions: string[];
  playerCounts: number[];
  textures: SelectOption[];
  preflopOptions: SelectOption[];
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const SAMPLE_BUCKETS: RiverBucketMeta[] = [
  { key: 'pct_0_25', label: '0-25%' },
  { key: 'pct_25_40', label: '25-40%' },
  { key: 'pct_40_60', label: '40-60%' },
  { key: 'pct_60_80', label: '60-80%' },
  { key: 'pct_80_100', label: '80-100%' },
  { key: 'pct_100_plus', label: '100%+' },
  { key: 'all_in', label: 'All-In' },
  { key: 'one_bb', label: '1 BB' },
];

const SAMPLE_SCENARIOS: PotScenario[] = [
  {
    heroPosition: 'BTN',
    betLine: 'triple_barrel',
    position: 'IP',
    playerCount: 2,
    textureKey: 'any',
    preflopKey: 'any',
    metrics: SAMPLE_BUCKETS.map((bucket, index) => ({
      bucketKey: bucket.key,
      bucketLabel: bucket.label,
      events: index % 3 === 0 ? 40 : 20,
      avgAddedBb: index % 3 === 0 ? 3.5 : 1.8,
    })),
  },
];

const SAMPLE_BET_LINES: SelectOption[] = [
  { key: 'triple_barrel', label: 'Double Barrel (B;B)' },
  { key: 'river_stab', label: 'IP Float Stab (C;X-B)' },
  { key: 'oop_xc_donk_lead', label: 'OOP XC Donk Lead (X-C;B)' },
];

const SAMPLE_POSITIONS: SelectOption[] = [
  { key: 'IP', label: 'In Position' },
  { key: 'OOP', label: 'Out of Position' },
];

const INITIAL_STATE: HookState = {
  data: [],
  bucketOrder: [],
  betLines: [],
  positions: [],
  heroPositions: [],
  playerCounts: [],
  textures: [],
  preflopOptions: [],
  loading: true,
  error: null,
  usingSample: false,
};

const transform = (payload: RawPayload): HookState => {
  const scenarios: PotScenario[] = payload.scenarios.map((scenario) => ({
    heroPosition: scenario.hero_position,
    betLine: scenario.bet_line,
    position: scenario.position,
    playerCount: scenario.player_count,
    textureKey: scenario.texture_key,
    preflopKey: scenario.preflop_key,
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
    betLines: payload.betting_lines,
    positions: payload.positions,
    heroPositions: payload.hero_positions,
    playerCounts: payload.player_counts,
    textures:
      payload.textures ?? [
        { key: 'any', label: 'All Textures' },
        { key: 'two_tone', label: 'Two Tone Rivers' },
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

const useRiverPotContribution = (sourceKey: string | null): HookState => {
  const [state, setState] = useState<HookState>(INITIAL_STATE);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const url =
          sourceKey && sourceKey.trim().length > 0
            ? `/api/river/pot-contribution?source=${encodeURIComponent(sourceKey)}`
            : '/api/river/pot-contribution';
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload: RawPayload = await response.json();
        if (!cancelled) {
          setState(transform(payload));
        }
      } catch (error) {
        console.error('Failed to load river pot contribution', error);
        if (!cancelled) {
          setState({
            data: SAMPLE_SCENARIOS,
            bucketOrder: SAMPLE_BUCKETS,
            betLines: SAMPLE_BET_LINES,
            positions: SAMPLE_POSITIONS,
            heroPositions: ['BTN'],
            playerCounts: [2],
            textures: [
              { key: 'any', label: 'All Textures' },
              { key: 'two_tone', label: 'Two Tone Rivers' },
            ],
            preflopOptions: [
              { key: 'any', label: 'All Preflop Pots' },
              { key: 'limped', label: 'Limped Pot (No Raise)' },
              { key: 'single_raise', label: 'Single-Raise Pot' },
              { key: 'three_bet_plus', label: '3-Bet+ Pot' },
            ],
            loading: false,
            error: 'Unable to load river pot contribution data. Displaying sample values.',
            usingSample: true,
          });
        }
      }
    };

    fetchData();
    return () => {
      cancelled = true;
    };
  }, [sourceKey]);

  return useMemo(() => state, [state]);
};

export default useRiverPotContribution;
