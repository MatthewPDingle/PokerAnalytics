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

export type LineResponderSeatSummary = {
  seat_label: string;
  responses: number;
  action_counts: Record<string, number>;
  hand_categories: Record<string, number>;
  bet_bucket_counts: Record<string, number>;
  relative_positions: Record<string, number>;
};

export type LineResponderSummary = {
  total_responses: number;
  action_counts: Record<string, number>;
  hand_categories: Record<string, number>;
  bet_bucket_counts: Record<string, number>;
  seats: LineResponderSeatSummary[];
};

export type LineActionSummary = {
  action_key: string | null;
  action_label: string | null;
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
  hand_categories: Record<string, number>;
  responder_summary: LineResponderSummary;
  hero_actions: Record<string, number>;
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
  action_summaries: LineActionSummary[];
  totals: LineActionSummary;
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
  { key: 'pct_100_plus', label: '100%+' },
  { key: 'all_in', label: 'All-In' },
  { key: 'one_bb', label: '1 BB' },
];

const RESPONDER_ACTION_KEYS = ['check', 'bet', 'call', 'raise', 'fold'] as const;

const createEmptyActionCounts = (): Record<string, number> =>
  RESPONDER_ACTION_KEYS.reduce<Record<string, number>>((accumulator, key) => {
    accumulator[key] = 0;
    return accumulator;
  }, {});

const mergeCounts = (target: Record<string, number>, source?: Partial<Record<string, number>>): void => {
  if (!source) {
    return;
  }
  Object.entries(source).forEach(([key, value]) => {
    if (value === undefined) {
      return;
    }
    target[key] = (target[key] ?? 0) + value;
  });
};

const createEmptySeatSummary = (seatLabel: string): LineResponderSeatSummary => ({
  seat_label: seatLabel,
  responses: 0,
  action_counts: createEmptyActionCounts(),
  hand_categories: {},
  bet_bucket_counts: {},
  relative_positions: {},
});

const emptyResponderSummary = (): LineResponderSummary => ({
  total_responses: 0,
  action_counts: createEmptyActionCounts(),
  hand_categories: {},
  bet_bucket_counts: {},
  seats: [],
});

type SampleResponderSeatInput = {
  seat_label: string;
  responses: number;
  action_counts?: Partial<Record<string, number>>;
  hand_categories?: Record<string, number>;
  bet_bucket_counts?: Record<string, number>;
  relative_positions?: Record<string, number>;
};

type SampleResponderInput = {
  totalResponses: number;
  actionCounts?: Partial<Record<string, number>>;
  handCategories?: Record<string, number>;
  betBucketCounts?: Record<string, number>;
  seats?: SampleResponderSeatInput[];
};

const createResponderSummary = (input: SampleResponderInput): LineResponderSummary => {
  const summary = emptyResponderSummary();
  summary.total_responses = input.totalResponses;
  mergeCounts(summary.action_counts, input.actionCounts);
  summary.hand_categories = { ...(input.handCategories ?? {}) };
  summary.bet_bucket_counts = { ...(input.betBucketCounts ?? {}) };
  summary.seats = (input.seats ?? []).map((seat) => {
    const entry = createEmptySeatSummary(seat.seat_label);
    entry.responses = seat.responses;
    mergeCounts(entry.action_counts, seat.action_counts);
    entry.hand_categories = { ...(seat.hand_categories ?? {}) };
    entry.bet_bucket_counts = { ...(seat.bet_bucket_counts ?? {}) };
    entry.relative_positions = { ...(seat.relative_positions ?? {}) };
    return entry;
  });
  return summary;
};

type SampleActionInput = {
  key: string;
  label: string;
  events: number;
  foldEvents: number;
  callEvents: number;
  raiseEvents: number;
  avgRatio: number;
  avgBet: number;
  avgAddedFlop: number;
  avgAddedAll: number;
  avgShare: number;
  handCategories: Record<string, number>;
  responderSummary: LineResponderSummary;
  heroActions: Record<string, number>;
};

const buildActionSummary = ({
  key,
  label,
  events,
  foldEvents,
  callEvents,
  raiseEvents,
  avgRatio,
  avgBet,
  avgAddedFlop,
  avgAddedAll,
  avgShare,
  handCategories,
  responderSummary,
  heroActions,
}: SampleActionInput): LineActionSummary => {
  const continueEvents = callEvents + raiseEvents;
  return {
    action_key: key,
    action_label: label,
    events,
    fold_events: foldEvents,
    call_events: callEvents,
    raise_events: raiseEvents,
    continue_events: continueEvents,
    fold_pct: events ? (foldEvents / events) * 100 : 0,
    call_pct: events ? (callEvents / events) * 100 : 0,
    raise_pct: events ? (raiseEvents / events) * 100 : 0,
    continue_pct: events ? (continueEvents / events) * 100 : 0,
    avg_ratio: avgRatio,
    avg_bet_bb: avgBet,
    avg_added_flop_bb: avgAddedFlop,
    avg_added_all_bb: avgAddedAll,
    avg_share_all: avgShare,
    hand_categories: handCategories,
    responder_summary: responderSummary,
    hero_actions: heroActions,
  };
};

const buildSampleTotals = (summaries: LineActionSummary[]): LineActionSummary => {
  let events = 0;
  let foldEvents = 0;
  let callEvents = 0;
  let raiseEvents = 0;
  let ratioSum = 0;
  let betSum = 0;
  let addedFlopSum = 0;
  let addedAllSum = 0;
  let shareSum = 0;

  const handTotals: Record<string, number> = {};
  const responderHandTotals: Record<string, number> = {};
  const responderBucketTotals: Record<string, number> = {};
  const responderActionTotals = createEmptyActionCounts();
  let responderResponses = 0;
  const seatAccumulator = new Map<string, LineResponderSeatSummary>();
  const heroActionTotals: Record<string, number> = {};

  summaries.forEach((summary) => {
    events += summary.events;
    foldEvents += summary.fold_events;
    callEvents += summary.call_events;
    raiseEvents += summary.raise_events;

    ratioSum += summary.avg_ratio * summary.events;
    betSum += summary.avg_bet_bb * summary.events;
    addedFlopSum += summary.avg_added_flop_bb * summary.events;
    addedAllSum += summary.avg_added_all_bb * summary.events;
    shareSum += summary.avg_share_all * summary.events;

    mergeCounts(handTotals, summary.hand_categories);

    const responder = summary.responder_summary;
    responderResponses += responder.total_responses;
    mergeCounts(responderActionTotals, responder.action_counts);
    mergeCounts(responderHandTotals, responder.hand_categories);
    mergeCounts(responderBucketTotals, responder.bet_bucket_counts);
    mergeCounts(heroActionTotals, summary.hero_actions);

    responder.seats.forEach((seat) => {
      const existing = seatAccumulator.get(seat.seat_label) ?? createEmptySeatSummary(seat.seat_label);
      existing.responses += seat.responses;
      mergeCounts(existing.action_counts, seat.action_counts);
      mergeCounts(existing.hand_categories, seat.hand_categories);
      mergeCounts(existing.bet_bucket_counts, seat.bet_bucket_counts);
      mergeCounts(existing.relative_positions, seat.relative_positions);
      seatAccumulator.set(seat.seat_label, existing);
    });
  });

  const continueEvents = callEvents + raiseEvents;
  const average = (value: number) => (events ? value / events : 0);

  return {
    action_key: 'all',
    action_label: 'All Actions',
    events,
    fold_events: foldEvents,
    call_events: callEvents,
    raise_events: raiseEvents,
    continue_events: continueEvents,
    fold_pct: events ? (foldEvents / events) * 100 : 0,
    call_pct: events ? (callEvents / events) * 100 : 0,
    raise_pct: events ? (raiseEvents / events) * 100 : 0,
    continue_pct: events ? (continueEvents / events) * 100 : 0,
    avg_ratio: average(ratioSum),
    avg_bet_bb: average(betSum),
    avg_added_flop_bb: average(addedFlopSum),
    avg_added_all_bb: average(addedAllSum),
    avg_share_all: average(shareSum),
    hand_categories: handTotals,
    responder_summary: {
      total_responses: responderResponses,
      action_counts: responderActionTotals,
      hand_categories: responderHandTotals,
      bet_bucket_counts: responderBucketTotals,
      seats: Array.from(seatAccumulator.values()).sort((a, b) => a.seat_label.localeCompare(b.seat_label)),
    },
    hero_actions: heroActionTotals,
  };
};

const SAMPLE_ACTION_SUMMARIES: LineActionSummary[] = SAMPLE_BUCKETS.map((bucket) =>
  buildActionSummary({
    key: bucket.key,
    label: bucket.label,
    events: 0,
    foldEvents: 0,
    callEvents: 0,
    raiseEvents: 0,
    avgRatio: 0,
    avgBet: 0,
    avgAddedFlop: 0,
    avgAddedAll: 0,
  avgShare: 0,
  handCategories: {},
  responderSummary: emptyResponderSummary(),
  heroActions: {},
}),
);

const SAMPLE_TOTALS = buildSampleTotals(SAMPLE_ACTION_SUMMARIES);

const SAMPLE_RESPONSE: LineQueryResponse = {
  version: 5,
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
  action_summaries: SAMPLE_ACTION_SUMMARIES,
  totals: SAMPLE_TOTALS,
  context: {
    total_events: 0,
    applied_filters: {},
    distributions: {},
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
