import { useEffect, useMemo, useState } from 'react';

export type LineDescriptorStep = {
  street: string;
  actor: string;
  action: string;
  qualifiers?: string[];
  sizing?: {
    bucket_keys?: string[];
    ratio_min?: number | null;
    ratio_max?: number | null;
    absolute_bb?: number | null;
    label?: string | null;
  } | null;
};

export type LineQueryRequest = {
  steps: LineDescriptorStep[];
  focus?: 'response' | 'hand_mix' | 'context' | string;
  annotation?: string;
  filters?: Record<string, unknown>;
};

export type LineBucketMeta = {
  key: string;
  label: string;
};

export type LineResponseMetric = {
  bucket_key: string;
  bucket_label: string;
  events: number;
  fold_events: number;
  call_events: number;
  raise_events: number;
  continue_events: number;
  fold_pct: number;
  call_pct: number;
  raise_pct: number;
  continue_pct: number;
  avg_ratio: number;
  avg_bet_bb: number;
  avg_added_flop_bb: number;
  avg_added_all_bb: number;
  avg_share_all: number;
};

export type LineHandMetric = {
  bucket_key: string;
  bucket_label: string;
  events: number;
  categories: Record<string, number>;
};

export type LineQueryResponse = {
  version: number;
  descriptor: {
    steps: Array<{
      street: string;
      actor: string;
      action: string;
      qualifiers?: string[];
      sizing?: {
        bucket_keys?: string[];
        ratio_min?: number | null;
        ratio_max?: number | null;
        absolute_bb?: number | null;
        label?: string | null;
      } | null;
    }>;
    focus: string;
    annotation?: string | null;
  };
  stake_policy: {
    token: string;
    allowed: number[] | null;
  };
  bucket_order: LineBucketMeta[];
  response_metrics: LineResponseMetric[];
  hand_metrics: LineHandMetric[];
  context: {
    total_events: number;
    applied_filters: Record<string, unknown>;
    distributions: Record<string, Array<{ key: string; count: number }>>;
  };
  fingerprint: string;
  descriptor_fingerprint?: string;
  request_filters?: Record<string, unknown>;
  using_sample: boolean;
};

type HookState = {
  data: LineQueryResponse | null;
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const INITIAL_STATE: HookState = {
  data: null,
  loading: false,
  error: null,
  usingSample: false,
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

const SAMPLE_RESPONSE: LineQueryResponse = {
  version: 2,
  descriptor: {
    steps: [
      { street: 'flop', actor: 'bettor', action: 'cbet', qualifiers: ['out_of_position'] },
      { street: 'flop', actor: 'responder', action: 'call', qualifiers: [] },
      {
        street: 'turn',
        actor: 'bettor',
        action: 'bet',
        qualifiers: ['out_of_position'],
        sizing: { bucket_keys: ['pct_40_60'] },
      },
    ],
    focus: 'response',
  },
  stake_policy: {
    token: 'sample',
    allowed: [0.1],
  },
  bucket_order: SAMPLE_BUCKETS,
  response_metrics: SAMPLE_BUCKETS.map((bucket) => {
    if (bucket.key === 'pct_40_60') {
      return {
        bucket_key: bucket.key,
        bucket_label: bucket.label,
        events: 48,
        fold_events: 18,
        call_events: 24,
        raise_events: 6,
        continue_events: 30,
        fold_pct: 37.5,
        call_pct: 50.0,
        raise_pct: 12.5,
        continue_pct: 62.5,
        avg_ratio: 0.52,
        avg_bet_bb: 5.6,
        avg_added_flop_bb: 1.3,
        avg_added_all_bb: 4.8,
        avg_share_all: 1.9,
      };
    }
    if (bucket.key === 'pct_25_40') {
      return {
        bucket_key: bucket.key,
        bucket_label: bucket.label,
        events: 28,
        fold_events: 8,
        call_events: 16,
        raise_events: 4,
        continue_events: 20,
        fold_pct: 28.6,
        call_pct: 57.1,
        raise_pct: 14.3,
        continue_pct: 71.4,
        avg_ratio: 0.34,
        avg_bet_bb: 3.8,
        avg_added_flop_bb: 1.1,
        avg_added_all_bb: 3.2,
        avg_share_all: 1.6,
      };
    }
    return {
      bucket_key: bucket.key,
      bucket_label: bucket.label,
      events: 0,
      fold_events: 0,
      call_events: 0,
      raise_events: 0,
      continue_events: 0,
      fold_pct: 0,
      call_pct: 0,
      raise_pct: 0,
      continue_pct: 0,
      avg_ratio: 0,
      avg_bet_bb: 0,
      avg_added_flop_bb: 0,
      avg_added_all_bb: 0,
      avg_share_all: 0,
    };
  }),
  hand_metrics: SAMPLE_BUCKETS.map((bucket) => {
    if (bucket.key === 'pct_40_60') {
      return {
        bucket_key: bucket.key,
        bucket_label: bucket.label,
        events: 48,
        categories: {
          Air: 14,
          'Underpair': 3,
          'Bottom Pair': 4,
          'Middle Pair': 6,
          'Top Pair': 10,
          Overpair: 2,
          'Two Pair': 3,
          'Trips/Set': 2,
          Straight: 1,
          Flush: 0,
          'Full House': 1,
          Quads: 0,
          'Flush Draw': 9,
          'OESD/DG': 7,
        },
      };
    }
    if (bucket.key === 'pct_25_40') {
      return {
        bucket_key: bucket.key,
        bucket_label: bucket.label,
        events: 28,
        categories: {
          Air: 6,
          'Underpair': 2,
          'Bottom Pair': 3,
          'Middle Pair': 5,
          'Top Pair': 7,
          Overpair: 1,
          'Two Pair': 2,
          'Trips/Set': 1,
          Straight: 1,
          Flush: 0,
          'Full House': 0,
          Quads: 0,
          'Flush Draw': 5,
          'OESD/DG': 4,
        },
      };
    }
    return {
      bucket_key: bucket.key,
      bucket_label: bucket.label,
      events: 0,
      categories: {
        Air: 0,
        'Underpair': 0,
        'Bottom Pair': 0,
        'Middle Pair': 0,
        'Top Pair': 0,
        Overpair: 0,
        'Two Pair': 0,
        'Trips/Set': 0,
        Straight: 0,
        Flush: 0,
        'Full House': 0,
        Quads: 0,
        'Flush Draw': 0,
        'OESD/DG': 0,
      },
    };
  }),
  context: {
    total_events: 76,
    applied_filters: {
      response_types: ['call'],
      positions: ['OOP'],
      bucket_keys: ['pct_40_60'],
      exclude_hero: true,
    },
    distributions: {
      line_keys: [
        { key: 'xc_turn_b', count: 48 },
        { key: 'c_turn_b', count: 28 },
      ],
    },
  },
  fingerprint: 'sample',
  descriptor_fingerprint: 'sample-descriptor',
  request_filters: { excludeHero: true },
  using_sample: true,
};

const cloneSampleResponse = (): LineQueryResponse => JSON.parse(JSON.stringify(SAMPLE_RESPONSE));

export const useLineQuery = (descriptor: LineQueryRequest | null) => {
  const [state, setState] = useState<HookState>(INITIAL_STATE);

  const descriptorKey = useMemo(
    () => (descriptor ? JSON.stringify(descriptor) : null),
    [descriptor],
  );

  useEffect(() => {
    if (!descriptor || !descriptorKey) {
      return;
    }

    const controller = new AbortController();
    setState((prev) => ({
      ...prev,
      loading: true,
      error: null,
      usingSample: false,
    }));

    const fetchData = async () => {
      try {
        const response = await fetch('/api/lines/query', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(descriptor),
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload = (await response.json()) as LineQueryResponse;
        if (controller.signal.aborted) {
          return;
        }
        setState({
          data: payload,
          loading: false,
          error: null,
          usingSample: Boolean(payload.using_sample),
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          data: cloneSampleResponse(),
          loading: false,
          error:
            error instanceof Error
              ? error.message
              : 'Unable to load line query data. Using sample payload.',
          usingSample: true,
        });
      }
    };

    fetchData();

    return () => {
      controller.abort();
    };
  }, [descriptor, descriptorKey]);

  return useMemo(() => state, [state]);
};

export default useLineQuery;
