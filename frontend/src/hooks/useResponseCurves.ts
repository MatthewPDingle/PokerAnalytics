import { useEffect, useMemo, useState } from 'react';

export type ResponseCurvePoint = {
  bucket_key: string;
  bucket_label: string;
  representative_ratio: number;
  fold_pct: number;
  call_pct: number;
  raise_pct: number;
  ev_bb: number;
  expected_final_pot_bb: number;
  expected_players_remaining: number;
};

export type ResponseCurveScenario = {
  id: string;
  hero_position: string;
  stack_bucket_key: string;
  stack_depth: string;
  villain_profile: string;
  vpip_ahead: number;
  players_behind: number;
  pot_bucket_key: string;
  pot_bucket: string;
  pot_size_bb: number;
  effective_stack_bb: number;
  sample_size: number;
  points: ResponseCurvePoint[];
  situation_key: string;
  situation_label: string;
};

export type StackBucketOption = { key: string; label: string };
export type PotBucketOption = { key: string; label: string };

const HERO_POSITION_ORDER = ['SB', 'BB', 'UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN'] as const;
const STACK_BUCKET_ORDER = ['bb_0_30', 'bb_30_60', 'bb_60_100', 'bb_100_plus'] as const;
const POT_BUCKET_ORDER = ['pot_blinds', 'pot_small', 'pot_medium', 'pot_large', 'pot_huge'] as const;

const BUCKET_META: Record<
  string,
  {
    label: string;
    ratio: number;
  }
> = {
  pct_0_25: { label: '0-25%', ratio: 0.125 },
  pct_25_40: { label: '25-40%', ratio: 0.325 },
  pct_40_60: { label: '40-60%', ratio: 0.5 },
  pct_60_80: { label: '60-80%', ratio: 0.7 },
  pct_80_100: { label: '80-100%', ratio: 0.9 },
  pct_100_125: { label: '100-125%', ratio: 1.125 },
  pct_125_200: { label: '125-200%', ratio: 1.6 },
  pct_200_300: { label: '200-300%', ratio: 2.5 },
  pct_300_plus: { label: '300%+ / All-In', ratio: 3.5 },
};

const point = (
  bucketKey: keyof typeof BUCKET_META,
  fold: number,
  call: number,
  raise: number,
  ev: number,
  finalPot: number,
  playersRemaining: number,
): ResponseCurvePoint => ({
  bucket_key: bucketKey,
  bucket_label: BUCKET_META[bucketKey].label,
  representative_ratio: BUCKET_META[bucketKey].ratio,
  fold_pct: fold,
  call_pct: call,
  raise_pct: raise,
  ev_bb: ev,
  expected_final_pot_bb: finalPot,
  expected_players_remaining: playersRemaining,
});

const SAMPLE_RESPONSE_CURVES: ResponseCurveScenario[] = [
  {
    id: 'btn_bb_30_60_vpip0_pot_blinds_players2',
    hero_position: 'BTN',
    stack_bucket_key: 'bb_30_60',
    stack_depth: '30-60 bb',
    villain_profile: 'Population',
    vpip_ahead: 0,
    players_behind: 2,
    pot_bucket_key: 'pot_blinds',
    pot_bucket: 'Blinds Only (~1.5 bb)',
    pot_size_bb: 1.5,
    effective_stack_bb: 45,
    sample_size: 1843,
    situation_key: 'folded_to_hero',
    situation_label: 'Folded to hero (blinds only)',
    points: [
      point('pct_0_25', 15, 68, 17, 6.2, 6.0, 2.0),
      point('pct_25_40', 19, 63, 18, 7.0, 6.5, 2.0),
      point('pct_40_60', 26, 57, 17, 7.6, 7.0, 2.0),
      point('pct_60_80', 34, 51, 15, 7.8, 7.5, 2.0),
      point('pct_80_100', 40, 46, 14, 7.4, 8.0, 2.0),
      point('pct_100_125', 51, 39, 10, 6.9, 8.5, 2.0),
      point('pct_125_200', 56, 35, 9, 6.3, 9.0, 2.0),
      point('pct_200_300', 61, 31, 8, 5.7, 9.5, 1.5),
      point('pct_300_plus', 67, 26, 7, 5.0, 10.0, 1.0),
    ],
  },
  {
    id: 'btn_bb_30_60_vpip1_pot_medium_players2',
    hero_position: 'BTN',
    stack_bucket_key: 'bb_30_60',
    stack_depth: '30-60 bb',
    villain_profile: 'Population',
    vpip_ahead: 1,
    players_behind: 2,
    pot_bucket_key: 'pot_medium',
    pot_bucket: '4-7 bb',
    pot_size_bb: 4.0,
    effective_stack_bb: 45,
    sample_size: 1320,
    situation_key: 'facing_single_raise',
    situation_label: 'Facing CO open to 2.5 bb (no callers)',
    points: [
      point('pct_25_40', 18, 49, 33, 5.8, 11.0, 2.5),
      point('pct_40_60', 24, 47, 29, 6.6, 11.5, 2.4),
      point('pct_60_80', 31, 43, 26, 6.9, 12.0, 2.3),
      point('pct_80_100', 39, 38, 23, 6.5, 12.5, 2.2),
      point('pct_100_125', 48, 33, 19, 6.1, 13.0, 2.0),
      point('pct_125_200', 53, 30, 17, 5.7, 13.5, 1.9),
      point('pct_200_300', 58, 27, 15, 5.2, 14.0, 1.7),
      point('pct_300_plus', 64, 23, 13, 4.7, 15.0, 1.5),
    ],
  },
  {
    id: 'hj_bb_60_100_vpip2_pot_small_players4',
    hero_position: 'HJ',
    stack_bucket_key: 'bb_60_100',
    stack_depth: '60-100 bb',
    villain_profile: 'Population',
    vpip_ahead: 2,
    players_behind: 4,
    pot_bucket_key: 'pot_small',
    pot_bucket: '2-4 bb',
    pot_size_bb: 3.5,
    effective_stack_bb: 80,
    sample_size: 1675,
    situation_key: 'facing_limpers',
    situation_label: 'Two limpers ahead',
    points: [
      point('pct_0_25', 12, 71, 17, 4.8, 6.5, 3.5),
      point('pct_25_40', 18, 65, 17, 5.4, 7.5, 3.4),
      point('pct_40_60', 26, 58, 16, 5.7, 8.5, 3.3),
      point('pct_60_80', 35, 51, 14, 5.6, 9.5, 3.0),
      point('pct_80_100', 43, 45, 12, 5.2, 10.5, 2.8),
      point('pct_100_125', 52, 38, 10, 4.7, 11.5, 2.6),
      point('pct_125_200', 58, 33, 9, 4.2, 12.5, 2.4),
      point('pct_200_300', 63, 29, 8, 3.8, 13.5, 2.2),
      point('pct_300_plus', 68, 24, 8, 3.3, 15.0, 2.0),
    ],
  },
  {
    id: 'bb_bb_100_plus_vpip1_pot_medium_players0',
    hero_position: 'BB',
    stack_bucket_key: 'bb_100_plus',
    stack_depth: '100+ bb',
    villain_profile: 'Population',
    vpip_ahead: 1,
    players_behind: 0,
    pot_bucket_key: 'pot_medium',
    pot_bucket: '4-7 bb',
    pot_size_bb: 4.5,
    effective_stack_bb: 125,
    sample_size: 1588,
    situation_key: 'facing_sb_open',
    situation_label: 'SB opens to 3 bb in blind-vs-blind',
    points: [
      point('pct_40_60', 26, 52, 22, 3.9, 8.5, 2.0),
      point('pct_60_80', 33, 48, 19, 4.1, 9.0, 2.0),
      point('pct_80_100', 40, 43, 17, 4.0, 9.5, 2.0),
      point('pct_100_125', 47, 39, 14, 3.8, 10.0, 2.0),
      point('pct_125_200', 54, 34, 12, 3.4, 10.5, 1.9),
      point('pct_200_300', 60, 30, 10, 3.0, 11.5, 1.8),
      point('pct_300_plus', 66, 26, 8, 2.6, 12.5, 1.6),
    ],
  },
];

const compareByOrder = (order: readonly string[]) => (a: string, b: string) => {
  const aIndex = order.indexOf(a);
  const bIndex = order.indexOf(b);
  const safeA = aIndex === -1 ? Number.MAX_SAFE_INTEGER : aIndex;
  const safeB = bIndex === -1 ? Number.MAX_SAFE_INTEGER : bIndex;
  if (safeA !== safeB) {
    return safeA - safeB;
  }
  return a.localeCompare(b);
};

export const useResponseCurves = () => {
  const [data, setData] = useState<ResponseCurveScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usingSample, setUsingSample] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch('/api/preflop/response-curves');
        if (!response.ok) {
          throw new Error(`Failed to load response curves: ${response.status}`);
        }
        const payload = (await response.json()) as ResponseCurveScenario[];
        if (!cancelled) {
          setData(payload);
          setUsingSample(false);
          setError(null);
        }
      } catch (err) {
        console.warn('Falling back to sample response-curve data', err);
        if (!cancelled) {
          setData(SAMPLE_RESPONSE_CURVES);
          setUsingSample(true);
          setError((err as Error).message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  const metadata = useMemo(() => {
    const heroPositionsSet = new Set<string>();
    const stackBucketMap = new Map<string, string>();
    const potBucketMap = new Map<string, string>();
    const playersBehindSet = new Set<number>();
    const vpipAheadSet = new Set<number>();

    data.forEach((scenario) => {
      heroPositionsSet.add(scenario.hero_position);
      stackBucketMap.set(scenario.stack_bucket_key, scenario.stack_depth);
      potBucketMap.set(scenario.pot_bucket_key, scenario.pot_bucket);
      playersBehindSet.add(scenario.players_behind);
      vpipAheadSet.add(scenario.vpip_ahead);
    });

    const heroPositions = Array.from(heroPositionsSet).sort(compareByOrder(HERO_POSITION_ORDER));
    const stackBuckets = Array.from(stackBucketMap.entries())
      .map(([key, label]) => ({ key, label }))
      .sort((a, b) => compareByOrder(STACK_BUCKET_ORDER)(a.key, b.key));
    const potBuckets = Array.from(potBucketMap.entries())
      .map(([key, label]) => ({ key, label }))
      .sort((a, b) => compareByOrder(POT_BUCKET_ORDER)(a.key, b.key));
    const playersBehindOptions = Array.from(playersBehindSet).sort((a, b) => a - b);
    const vpipAheadOptions = Array.from(vpipAheadSet).sort((a, b) => a - b);

    return {
      heroPositions,
      stackBuckets,
      potBuckets,
      playersBehindOptions,
      vpipAheadOptions,
    };
  }, [data]);

  return {
    data,
    loading,
    error,
    usingSample,
    heroPositions: metadata.heroPositions,
    stackBuckets: metadata.stackBuckets,
    potBuckets: metadata.potBuckets,
    playersBehindOptions: metadata.playersBehindOptions,
    vpipAheadOptions: metadata.vpipAheadOptions,
  };
};
