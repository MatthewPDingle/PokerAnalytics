import {
  Alert,
  AlertIcon,
  Box,
  Divider,
  Flex,
  Heading,
  Spinner,
  Stack,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  FormControl,
  FormLabel,
  Select,
} from '@chakra-ui/react';
import { useMemo, useReducer, useState } from 'react';

import ActionMatrixComposer, { BucketOption, HighlightContextSummary } from '../components/ActionMatrixComposer';
import useLineQuery, { LineBucketMeta, LineResponseMetric, LineHandMetric } from '../hooks/useLineQuery';
import {
  createInitialTableComposerState,
  deriveDescriptorFromTable,
  tableComposerReducer,
} from '../state/tableComposer';

const NORMALIZED_BUCKETS: LineBucketMeta[] = [
  { key: 'check', label: 'Check' },
  { key: 'pct_0_25', label: '0-25%' },
  { key: 'pct_25_40', label: '25-40%' },
  { key: 'pct_40_60', label: '40-60%' },
  { key: 'pct_60_80', label: '60-80%' },
  { key: 'pct_80_100', label: '80-100%' },
  { key: 'pct_100_plus', label: '100%+' },
  { key: 'one_bb', label: '1 BB' },
  { key: 'all_in', label: 'All-In' },
];

const DEFAULT_BUCKETS: LineBucketMeta[] = NORMALIZED_BUCKETS.map((bucket) => ({ ...bucket }));

const LEGACY_BUCKET_KEY_MAP: Record<string, string> = {
  check: 'check',
  pct_0_25: 'pct_0_25',
  pct_25_40: 'pct_25_40',
  pct_40_60: 'pct_40_60',
  pct_60_80: 'pct_60_80',
  pct_80_100: 'pct_80_100',
  pct_100_plus: 'pct_100_plus',
  pct_100_125: 'pct_100_plus',
  pct_125_200: 'pct_100_plus',
  pct_200_300: 'pct_100_plus',
  pct_300_plus: 'pct_100_plus',
  pct_125_plus: 'pct_100_plus',
  pct_125_150: 'pct_100_plus',
  pct_150_200: 'pct_100_plus',
  pct_300_400: 'pct_100_plus',
  all_in: 'all_in',
  one_bb: 'one_bb',
};

const NORMALIZED_BUCKET_KEY_SET = new Set(NORMALIZED_BUCKETS.map((bucket) => bucket.key));

const NORMALIZED_TO_SOURCE_KEYS: Record<string, string[]> = {
  check: ['check'],
  pct_0_25: ['pct_0_25'],
  pct_25_40: ['pct_25_40'],
  pct_40_60: ['pct_40_60'],
  pct_60_80: ['pct_60_80'],
  pct_80_100: ['pct_80_100'],
  pct_100_plus: ['pct_100_125', 'pct_125_200', 'pct_200_300', 'pct_300_plus', 'pct_125_plus', 'pct_125_150', 'pct_150_200', 'pct_300_400'],
  one_bb: ['one_bb'],
  all_in: ['all_in'],
};

type HandDefinition = { key: string; label: string; members: string[] };

const HAND_TYPE_DEFINITIONS: HandDefinition[] = [
  { key: 'air', label: 'Air', members: ['Air'] },
  { key: 'underpair', label: 'Underpair', members: ['Underpair'] },
  { key: 'bottom_pair', label: 'Bottom Pair', members: ['Bottom Pair'] },
  { key: 'middle_pair', label: 'Middle Pair', members: ['Middle Pair'] },
  { key: 'top_pair', label: 'Top Pair', members: ['Top Pair'] },
  { key: 'overpair', label: 'Overpair', members: ['Overpair'] },
  { key: 'two_pair', label: 'Two Pair', members: ['Two Pair'] },
  { key: 'trips_set', label: 'Trips/Set', members: ['Trips/Set'] },
  { key: 'straight', label: 'Straight', members: ['Straight'] },
  { key: 'flush', label: 'Flush', members: ['Flush'] },
  { key: 'full_house', label: 'Full House', members: ['Full House'] },
  { key: 'quads', label: 'Quads', members: ['Quads'] },
  { key: 'flush_draw', label: 'Flush Draw', members: ['Flush Draw'] },
  { key: 'oesd_dg', label: 'OESD/DG', members: ['OESD/DG'] },
];

const HAND_GROUP_DEFINITIONS: HandDefinition[] = [
  { key: 'air', label: 'Air', members: ['Air'] },
  { key: 'weak_pair', label: 'Weak Pair', members: ['Underpair', 'Bottom Pair', 'Middle Pair'] },
  { key: 'top_pair', label: 'Top Pair', members: ['Top Pair'] },
  { key: 'overpair', label: 'Overpair', members: ['Overpair'] },
  { key: 'two_pair', label: 'Two Pair', members: ['Two Pair'] },
  { key: 'trips_set', label: 'Trips/Set', members: ['Trips/Set'] },
  { key: 'monster', label: 'Monster', members: ['Straight', 'Flush', 'Full House', 'Quads'] },
  { key: 'draw', label: 'Draw', members: ['Flush Draw', 'OESD/DG'] },
];

const TABLE_SIZE_OPTIONS = Array.from({ length: 9 }, (_, index) => index + 2);

const POT_ODDS_BUCKET_RANGES: Record<string, { min: number; max?: number }> = {
  '0-25%': { min: 0, max: 0.25 },
  '25-40%': { min: 0.25, max: 0.4 },
  '40-60%': { min: 0.4, max: 0.6 },
  '60-80%': { min: 0.6, max: 0.8 },
  '80-100%': { min: 0.8, max: 1.0 },
  '100%+': { min: 1.0 },
};

const TEXTURE_LABEL_TO_KEY: Record<string, string> = {
  Rainbow: 'rainbow',
  Monotone: 'monotone',
  'Two Tone': 'two_tone',
  Paired: 'paired',
  'Connected (≤4 Gap)': 'connected',
  'Ace High': 'ace_high',
  'Low (≤ Ten)': 'low',
  'High Broadway': 'high_broadway',
};

type DerivedRequestFilters = {
  bucketKeys?: string[];
  textureKeys?: string[];
  playersDealt?: number[];
  playerCounts?: number[];
  playersRemaining?: number[];
  heroPositions?: string[];
  relativePositions?: string[];
  ratioMin?: number | null;
  ratioMax?: number | null;
  minPreflopRaises?: number | null;
  allInCalled?: boolean;
  lineKeys?: string[];
  effectiveStackBuckets?: string[];
  sprBuckets?: string[];
};

type DerivedFilterParseResult = {
  filters: DerivedRequestFilters;
  highlightedColumns: Set<string>;
};

const parseHighlightFilters = (context: HighlightContextSummary | null): DerivedFilterParseResult => {
  const highlightedColumns = new Set<string>();

  if (!context) {
    return { filters: {}, highlightedColumns };
  }

  const activeIds = new Set(context.activeFilterIds ?? []);
  const isActive = (id?: string) => !id || activeIds.has(id);

  const bucketKeys = new Set<string>();
  const textureKeys = new Set<string>();
  const playersDealt = new Set<number>();
  const playerCounts = new Set<number>();
  const playersRemaining = new Set<number>();
  const heroPositions = new Set<string>();
  const relativePositions = new Set<string>();
  const lineKeys = new Set<string>();
  const effectiveStackBuckets = new Set<string>();
  const sprBuckets = new Set<string>();

  let ratioMin: number | null = null;
  let ratioMax: number | null = null;
  let minPreflopRaises: number | null = null;
  let allInCalled = false;

  const applyRatioRange = (range: { min: number; max?: number }) => {
    if (range.min !== undefined) {
      ratioMin = ratioMin !== null ? Math.max(ratioMin, range.min) : range.min;
    }
    if (range.max !== undefined) {
      ratioMax = ratioMax !== null ? Math.min(ratioMax, range.max) : range.max;
    }
  };

  const parseIntegerSuffix = (label: string, prefix: string): number | null => {
    const value = label.slice(prefix.length).trim();
    const parsed = parseInt(value, 10);
    return Number.isFinite(parsed) ? parsed : null;
  };

  if (context.bet?.bucketKey && isActive(context.bet.filterId)) {
    bucketKeys.add(context.bet.bucketKey);
    highlightedColumns.add(context.bet.bucketKey);
  }

  if (context.facing?.bucketKey && isActive(context.facing.filterId)) {
    bucketKeys.add(context.facing.bucketKey);
    highlightedColumns.add(context.facing.bucketKey);
  }

  if (context.actionType === 'check') {
    highlightedColumns.add('check');
  }

  context.filters?.categories.forEach((category) => {
    category.filters.forEach((filter) => {
      if (!isActive(filter.id)) {
        return;
      }
      if (category.key === 'line') {
        const detail = (filter.detail ?? '').trim();
        if (detail) {
          lineKeys.add(detail);
        } else if (filter.label.startsWith('Line: ')) {
          lineKeys.add(filter.label.slice('Line: '.length).trim().toLowerCase());
        }
        return;
      }
      if (category.key === 'stack') {
        if (filter.label.startsWith('Effective Stack: ')) {
          const bucket = filter.label.slice('Effective Stack: '.length).trim();
          if (bucket) {
            effectiveStackBuckets.add(bucket);
          }
          return;
        }
        if (filter.label.startsWith('SPR Bucket: ')) {
          const bucket = filter.label.slice('SPR Bucket: '.length).trim();
          if (bucket) {
            sprBuckets.add(bucket);
          }
          return;
        }
      }
      const { label } = filter;
      if (label.startsWith('Players Dealt: ')) {
        const value = parseIntegerSuffix(label, 'Players Dealt: ');
        if (value !== null) {
          playersDealt.add(value);
        }
        return;
      }
      if (label.startsWith('Players Remaining: ')) {
        const value = parseIntegerSuffix(label, 'Players Remaining: ');
        if (value !== null) {
          playerCounts.add(value);
          playersRemaining.add(value);
        }
        return;
      }
      if (label.startsWith('Player Position: ')) {
        heroPositions.add(label.slice('Player Position: '.length).trim().toUpperCase());
        return;
      }
      if (label.startsWith('Relative Position: ')) {
        relativePositions.add(label.slice('Relative Position: '.length).trim().toLowerCase());
        return;
      }
      if (label === '3-Bet Pot') {
        minPreflopRaises = Math.max(minPreflopRaises ?? 0, 2);
        return;
      }
      if (label === '4-Bet Pot') {
        minPreflopRaises = Math.max(minPreflopRaises ?? 0, 3);
        return;
      }
      if (label === '5+ Bet Pot') {
        minPreflopRaises = Math.max(minPreflopRaises ?? 0, 4);
        return;
      }
      if (label === 'All-In Called') {
        allInCalled = true;
        return;
      }
      if (label === 'All-In') {
        bucketKeys.add('all_in');
        highlightedColumns.add('all_in');
        return;
      }
      if (label.startsWith('Pot Odds: ')) {
        const bucket = label.slice('Pot Odds: '.length).trim();
        const range = POT_ODDS_BUCKET_RANGES[bucket];
        if (range) {
          applyRatioRange(range);
        }
        return;
      }
    });
  });

  context.filters?.boardCategories.forEach((category) => {
    if (category.key !== 'flop') {
      return;
    }
    category.filters.forEach((filter) => {
      if (!isActive(filter.id)) {
        return;
      }
      const key = TEXTURE_LABEL_TO_KEY[filter.label];
      if (key) {
        textureKeys.add(key);
      }
    });
  });

  if (bucketKeys.size === 0 && context.actionType !== 'check') {
    // no active bucket filters; ensure highlighted columns still reflect facing/bet states for context
    if (context.bet?.bucketKey) {
      highlightedColumns.add(context.bet.bucketKey);
    }
    if (context.facing?.bucketKey) {
      highlightedColumns.add(context.facing.bucketKey);
    }
  }

  const filters: DerivedRequestFilters = {};
  if (bucketKeys.size > 0) {
    filters.bucketKeys = Array.from(bucketKeys);
  }
  if (textureKeys.size > 0) {
    filters.textureKeys = Array.from(textureKeys);
  }
  if (playersDealt.size > 0) {
    filters.playersDealt = Array.from(playersDealt);
  }
  if (playerCounts.size > 0) {
    filters.playerCounts = Array.from(playerCounts);
  }
  if (playersRemaining.size > 0) {
    filters.playersRemaining = Array.from(playersRemaining);
  }
  if (heroPositions.size > 0) {
    filters.heroPositions = Array.from(heroPositions);
  }
  if (relativePositions.size > 0) {
    filters.relativePositions = Array.from(relativePositions);
  }
  if (ratioMin !== null) {
    filters.ratioMin = ratioMin;
  }
  if (ratioMax !== null) {
    filters.ratioMax = ratioMax;
  }
  if (minPreflopRaises !== null) {
    filters.minPreflopRaises = minPreflopRaises;
  }
  if (allInCalled) {
    filters.allInCalled = true;
  }
  if (lineKeys.size > 0) {
    filters.lineKeys = Array.from(lineKeys);
  }
  if (effectiveStackBuckets.size > 0) {
    filters.effectiveStackBuckets = Array.from(effectiveStackBuckets);
  }
  if (sprBuckets.size > 0) {
    filters.sprBuckets = Array.from(sprBuckets);
  }

  return { filters, highlightedColumns };
};

const derivePercentColor = (value: number, columnMax: number) => {
  if (columnMax <= 0 || value <= 0) {
    return { bg: 'white', color: 'gray.800' };
  }
  const intensity = Math.min(Math.max(value / columnMax, 0), 1);
  const base = { r: 66, g: 153, b: 225 };
  const r = Math.round(255 - (255 - base.r) * intensity);
  const g = Math.round(255 - (255 - base.g) * intensity);
  const b = Math.round(255 - (255 - base.b) * intensity);
  const textColor = intensity > 0.65 ? 'white' : 'gray.900';
  return { bg: `rgb(${r}, ${g}, ${b})`, color: textColor };
};

const deriveCountColor = (value: number, max: number) => {
  if (max <= 0 || value <= 0) {
    return { bg: 'white', color: 'gray.800' };
  }
  const intensity = Math.min(Math.max(value / max, 0), 1);
  const base = { r: 56, g: 161, b: 105 };
  const r = Math.round(255 - (255 - base.r) * intensity);
  const g = Math.round(255 - (255 - base.g) * intensity);
  const b = Math.round(255 - (255 - base.b) * intensity);
  const textColor = intensity > 0.6 ? 'white' : 'gray.900';
  return { bg: `rgb(${r}, ${g}, ${b})`, color: textColor };
};

const deriveRowGradient = (value: number, rowMax: number, palette: 'orange' | 'red', rowMin = 0) => {
  if (rowMax <= rowMin || value <= rowMin) {
    return { bg: 'white', color: 'gray.800' };
  }
  const range = rowMax - rowMin;
  const intensity = Math.min(Math.max((value - rowMin) / range, 0), 1);
  const base = palette === 'orange' ? { r: 237, g: 137, b: 54 } : { r: 229, g: 62, b: 62 };
  const r = Math.round(255 - (255 - base.r) * intensity);
  const g = Math.round(255 - (255 - base.g) * intensity);
  const b = Math.round(255 - (255 - base.b) * intensity);
  const textColor = intensity > 0.6 ? 'white' : 'gray.900';
  return { bg: `rgb(${r}, ${g}, ${b})`, color: textColor };
};

type ResponseAccumulator = {
  events: number;
  foldEvents: number;
  callEvents: number;
  raiseEvents: number;
  continueEvents: number;
  ratioWeighted: number;
  betWeighted: number;
  addedFlopWeighted: number;
  addedAllWeighted: number;
  shareWeighted: number;
};

type HandAccumulator = {
  events: number;
  categories: Map<string, number>;
};

const createResponseAccumulator = (): ResponseAccumulator => ({
  events: 0,
  foldEvents: 0,
  callEvents: 0,
  raiseEvents: 0,
  continueEvents: 0,
  ratioWeighted: 0,
  betWeighted: 0,
  addedFlopWeighted: 0,
  addedAllWeighted: 0,
  shareWeighted: 0,
});

const createHandAccumulator = (): HandAccumulator => ({ events: 0, categories: new Map() });

const normaliseBucketKey = (key: string) => LEGACY_BUCKET_KEY_MAP[key] ?? key;

const normalizeLineResults = (
  _bucketOrder: LineBucketMeta[],
  responseMetrics: LineResponseMetric[],
  handMetrics: LineHandMetric[],
) => {
  const responseAggregates = new Map<string, ResponseAccumulator>();

  responseMetrics.forEach((metric) => {
    const mappedKey = normaliseBucketKey(metric.bucket_key);
    if (!NORMALIZED_BUCKET_KEY_SET.has(mappedKey)) {
      return;
    }
    const accumulator = responseAggregates.get(mappedKey) ?? createResponseAccumulator();
    responseAggregates.set(mappedKey, accumulator);

    const events = metric.events ?? 0;
    accumulator.events += events;
    accumulator.foldEvents += metric.fold_events ?? 0;
    accumulator.callEvents += metric.call_events ?? 0;
    accumulator.raiseEvents += metric.raise_events ?? 0;
    accumulator.continueEvents += metric.continue_events ?? 0;
    accumulator.ratioWeighted += (metric.avg_ratio ?? 0) * events;
    accumulator.betWeighted += (metric.avg_bet_bb ?? 0) * events;
    accumulator.addedFlopWeighted += (metric.avg_added_flop_bb ?? 0) * events;
    accumulator.addedAllWeighted += (metric.avg_added_all_bb ?? 0) * events;
    accumulator.shareWeighted += (metric.avg_share_all ?? 0) * events;
  });

  const normalisedResponseMetrics: LineResponseMetric[] = NORMALIZED_BUCKETS.map(({ key, label }) => {
    const aggregate = responseAggregates.get(key);
    const events = aggregate?.events ?? 0;
    const foldEvents = aggregate?.foldEvents ?? 0;
    const callEvents = aggregate?.callEvents ?? 0;
    const raiseEvents = aggregate?.raiseEvents ?? 0;
    const continueEvents = aggregate?.continueEvents ?? 0;
    const avgRatio = aggregate && aggregate.events > 0 ? aggregate.ratioWeighted / aggregate.events : 0;
    const avgBet = aggregate && aggregate.events > 0 ? aggregate.betWeighted / aggregate.events : 0;
    const avgAddedFlop = aggregate && aggregate.events > 0 ? aggregate.addedFlopWeighted / aggregate.events : 0;
    const avgAddedAll = aggregate && aggregate.events > 0 ? aggregate.addedAllWeighted / aggregate.events : 0;
    const avgShareAll = aggregate && aggregate.events > 0 ? aggregate.shareWeighted / aggregate.events : 0;

    return {
      bucket_key: key,
      bucket_label: label,
      events,
      fold_events: foldEvents,
      call_events: callEvents,
      raise_events: raiseEvents,
      continue_events: continueEvents,
      fold_pct: events > 0 ? (foldEvents / events) * 100 : 0,
      call_pct: events > 0 ? (callEvents / events) * 100 : 0,
      raise_pct: events > 0 ? (raiseEvents / events) * 100 : 0,
      continue_pct: events > 0 ? (continueEvents / events) * 100 : 0,
      avg_ratio: avgRatio,
      avg_bet_bb: avgBet,
      avg_added_flop_bb: avgAddedFlop,
      avg_added_all_bb: avgAddedAll,
      avg_share_all: avgShareAll,
    };
  });

  const handAggregates = new Map<string, HandAccumulator>();
  handMetrics.forEach((metric) => {
    const mappedKey = normaliseBucketKey(metric.bucket_key);
    if (!NORMALIZED_BUCKET_KEY_SET.has(mappedKey)) {
      return;
    }
    const accumulator = handAggregates.get(mappedKey) ?? createHandAccumulator();
    handAggregates.set(mappedKey, accumulator);
    const events = metric.events ?? 0;
    accumulator.events += events;
    Object.entries(metric.categories ?? {}).forEach(([category, count]) => {
      accumulator.categories.set(category, (accumulator.categories.get(category) ?? 0) + count);
    });
  });

  const normalisedHandMetrics: LineHandMetric[] = NORMALIZED_BUCKETS.map(({ key, label }) => {
    const aggregate = handAggregates.get(key);
    const categories: Record<string, number> = {};
    if (aggregate) {
      aggregate.categories.forEach((count, category) => {
        categories[category] = count;
      });
    }
    return {
      bucket_key: key,
      bucket_label: label,
      events: aggregate?.events ?? 0,
      categories,
    };
  });

  return {
    bucketOrder: NORMALIZED_BUCKETS.map((bucket) => ({ ...bucket })),
    responseMetrics: normalisedResponseMetrics,
    handMetrics: normalisedHandMetrics,
  };
};

const LineExplorer = () => {
  const [composerState, dispatch] = useReducer(tableComposerReducer, undefined, () => createInitialTableComposerState());
  const [highlightContext, setHighlightContext] = useState<HighlightContextSummary | null>(null);
  const [groupedResponderView, setGroupedResponderView] = useState(true);
  const parsedHighlight = useMemo(() => parseHighlightFilters(highlightContext), [highlightContext]);

  const descriptorPayload = useMemo(() => {
    const base = deriveDescriptorFromTable(composerState);
    const combinedFilters: Record<string, unknown> = {
      ...(base.filters ?? {}),
      excludeHero: true,
    };

    const { filters: derivedFilters } = parsedHighlight;

    if (derivedFilters.bucketKeys && derivedFilters.bucketKeys.length > 0) {
      const expanded = new Set<string>();
      derivedFilters.bucketKeys.forEach((bucketKey) => {
        const mapped = NORMALIZED_TO_SOURCE_KEYS[bucketKey];
        if (mapped && mapped.length) {
          mapped.forEach((value) => expanded.add(value));
        } else {
          expanded.add(bucketKey);
        }
      });
      combinedFilters.bucket_keys = Array.from(expanded);
    } else {
      delete combinedFilters.bucket_keys;
    }

    if (derivedFilters.textureKeys && derivedFilters.textureKeys.length > 0) {
      combinedFilters.textureKeys = derivedFilters.textureKeys;
    } else {
      delete combinedFilters.textureKeys;
    }

    if (derivedFilters.playersDealt && derivedFilters.playersDealt.length > 0) {
      combinedFilters.playersDealt = derivedFilters.playersDealt;
    } else {
      delete combinedFilters.playersDealt;
    }

    if (derivedFilters.playerCounts && derivedFilters.playerCounts.length > 0) {
      combinedFilters.playerCounts = derivedFilters.playerCounts;
    } else {
      delete combinedFilters.playerCounts;
    }

    if (derivedFilters.playersRemaining && derivedFilters.playersRemaining.length > 0) {
      combinedFilters.playersRemaining = derivedFilters.playersRemaining;
    } else {
      delete combinedFilters.playersRemaining;
    }

    if (derivedFilters.heroPositions && derivedFilters.heroPositions.length > 0) {
      combinedFilters.heroPositions = derivedFilters.heroPositions;
    } else {
      delete combinedFilters.heroPositions;
    }

    if (derivedFilters.relativePositions && derivedFilters.relativePositions.length > 0) {
      combinedFilters.relativePositions = derivedFilters.relativePositions;
    } else {
      delete combinedFilters.relativePositions;
    }

    if (derivedFilters.effectiveStackBuckets && derivedFilters.effectiveStackBuckets.length > 0) {
      combinedFilters.effectiveStackBuckets = derivedFilters.effectiveStackBuckets;
    } else {
      delete combinedFilters.effectiveStackBuckets;
    }

    if (derivedFilters.sprBuckets && derivedFilters.sprBuckets.length > 0) {
      combinedFilters.sprBuckets = derivedFilters.sprBuckets;
    } else {
      delete combinedFilters.sprBuckets;
    }

    if (derivedFilters.ratioMin !== null && derivedFilters.ratioMin !== undefined) {
      combinedFilters.ratioMin = derivedFilters.ratioMin;
    } else {
      delete combinedFilters.ratioMin;
    }

    if (derivedFilters.ratioMax !== null && derivedFilters.ratioMax !== undefined) {
      combinedFilters.ratioMax = derivedFilters.ratioMax;
    } else {
      delete combinedFilters.ratioMax;
    }

    if (derivedFilters.minPreflopRaises !== null && derivedFilters.minPreflopRaises !== undefined) {
      combinedFilters.minPreflopRaises = derivedFilters.minPreflopRaises;
    } else {
      delete combinedFilters.minPreflopRaises;
    }

    if (derivedFilters.allInCalled) {
      combinedFilters.allInCalled = true;
    } else {
      delete combinedFilters.allInCalled;
    }

    if (derivedFilters.lineKeys && derivedFilters.lineKeys.length > 0) {
      combinedFilters.lineKeys = derivedFilters.lineKeys;
    } else {
      delete combinedFilters.lineKeys;
    }

    return {
      ...base,
      filters: combinedFilters,
    };
  }, [composerState, parsedHighlight]);

  const shouldQuery = highlightContext !== null;
  const { data, loading, error, usingSample } = useLineQuery(shouldQuery ? descriptorPayload : null);
  const isLoadingResults = shouldQuery && loading;

  const rawBucketOrder = data?.bucket_order ?? DEFAULT_BUCKETS;
  const rawResponseMetrics = data?.response_metrics ?? [];
  const rawHandMetrics = data?.hand_metrics ?? [];

  const { bucketOrder, responseMetrics, handMetrics } = useMemo(
    () => normalizeLineResults(rawBucketOrder, rawResponseMetrics, rawHandMetrics),
    [rawBucketOrder, rawResponseMetrics, rawHandMetrics],
  );
  const totalEvents = data?.context?.total_events ?? 0;

  const descriptorSteps = shouldQuery ? data?.descriptor?.steps ?? descriptorPayload.steps : [];
  const bucketOptions: BucketOption[] = useMemo(
    () => bucketOrder.filter((bucket) => bucket.key !== 'check').map((bucket) => ({ key: bucket.key, label: bucket.label })),
    [bucketOrder],
  );

  const highlightedColumns = parsedHighlight.highlightedColumns;

  return (
    <Box as="main" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
      <Stack spacing={8} maxW="1200px" mx="auto">
        <Stack spacing={3}>
          <Heading size="lg">Line Explorer</Heading>
          <Text color="whiteAlpha.800">
            Assign actions to each seat across streets and inspect the corresponding population responses.
          </Text>
        </Stack>

        <Stack spacing={4} borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" p={{ base: 4, md: 6 }}>
          <Flex justify="space-between" align={{ base: 'flex-start', md: 'center' }} wrap="wrap" gap={4}>
            <Text fontWeight="semibold">Action Matrix Composer</Text>
            <Flex align="center" gap={4} wrap="wrap">
              <FormControl width="auto">
                <FormLabel htmlFor="table-size-select" mb="0" fontSize="sm">
                  Table size
                </FormLabel>
                <Select
                  id="table-size-select"
                  size="sm"
                  value={composerState.tableSize}
                  onChange={(event) => dispatch({ type: 'set_table_size', size: Number(event.target.value) })}
                >
                  {TABLE_SIZE_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option} players
                    </option>
                  ))}
                </Select>
              </FormControl>
            </Flex>
          </Flex>

          <ActionMatrixComposer
            state={composerState}
            dispatch={dispatch}
            bucketOptions={bucketOptions}
            onHighlightContextChange={setHighlightContext}
          />
        </Stack>

        {error && usingSample && (
          <Alert status="warning" variant="left-accent">
            <AlertIcon />
            Using sample payload (API unavailable). Configure the matrix to explore mock data.
          </Alert>
        )}

        {error && !usingSample && (
          <Alert status="error" variant="left-accent">
            <AlertIcon />
            {error}
          </Alert>
        )}

        {loading && shouldQuery && !data && (
          <Flex align="center" justify="center" minH="40vh">
            <Spinner size="xl" />
          </Flex>
        )}

        {!shouldQuery && (
          <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.300" p={{ base: 6, md: 8 }}>
            <Stack spacing={3} align="center" textAlign="center">
              <Heading size="md">Select a Player</Heading>
              <Text color="whiteAlpha.800">
                Highlight a seat in the Action Matrix Composer to generate derived filters and population summaries.
              </Text>
            </Stack>
          </Box>
        )}

        {shouldQuery && data && (
          <Box position="relative">
            {isLoadingResults && (
              <Flex
                position="absolute"
                inset={0}
                align="center"
                justify="center"
                bg="blackAlpha.600"
                zIndex={2}
              >
                <Spinner size="xl" />
              </Flex>
            )}
            <Stack
              spacing={6}
              opacity={isLoadingResults ? 0.5 : 1}
              pointerEvents={isLoadingResults ? 'none' : 'auto'}
              transition="opacity 0.2s ease"
            >
              <ContextSummary totalEvents={totalEvents} steps={descriptorSteps} excludeHero={composerState.excludeHero} />

              <Stack spacing={4}>
                <Heading size="md">Response Metrics</Heading>
                <ResponseTable bucketOrder={bucketOrder} metrics={responseMetrics} highlightedColumns={highlightedColumns} />
            </Stack>

            <Divider />

            <Stack spacing={4}>
              <Flex align="center" justify="space-between" wrap="wrap" gap={3}>
                <Heading size="md">Responder Hand Breakdown</Heading>
                <FormControl display="flex" alignItems="center" width="auto">
                  <FormLabel htmlFor="responder-hand-grouped-toggle" mb="0" fontSize="sm">
                    Grouped View
                  </FormLabel>
                  <Switch
                    id="responder-hand-grouped-toggle"
                    size="sm"
                    isChecked={groupedResponderView}
                    onChange={(event) => setGroupedResponderView(event.target.checked)}
                    colorScheme="purple"
                  />
                </FormControl>
              </Flex>
              <HandBreakdownTable
                bucketOrder={bucketOrder}
                metrics={handMetrics}
                highlightedColumns={highlightedColumns}
                groupedView={groupedResponderView}
              />
              </Stack>
            </Stack>
          </Box>
        )}
      </Stack>
    </Box>
  );
};

const ContextSummary = ({
  totalEvents,
  steps,
  excludeHero,
}: {
  totalEvents: number;
  steps: Array<{
    street: string;
    actor: string;
    action: string;
    qualifiers?: string[];
    sizing?: { bucket_keys?: string[]; ratio_min?: number | null; ratio_max?: number | null; absolute_bb?: number | null; label?: string | null } | null;
  }>;
  excludeHero: boolean;
}) => (
  <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" p={{ base: 4, md: 6 }}>
    <Stack spacing={2}>
      <Text fontSize="sm" color="whiteAlpha.700" textTransform="uppercase" letterSpacing="wider">
        Scenario Summary
      </Text>
      <Text color="whiteAlpha.900">{totalEvents.toLocaleString()} matching events.</Text>
      <Text color="whiteAlpha.800" fontSize="sm">
        {excludeHero ? 'Hero hands excluded.' : 'Hero hands included.'}
      </Text>
      <Stack spacing={1} color="whiteAlpha.800" fontSize="sm">
        {steps.map((step, index) => (
          <Text key={`${step.street}-${index}`}>
            {step.street.toUpperCase()}: {step.actor} {step.action}
          </Text>
        ))}
      </Stack>
    </Stack>
  </Box>
);

const ResponseTable = ({
  bucketOrder,
  metrics,
  highlightedColumns,
}: {
  bucketOrder: LineBucketMeta[];
  metrics: LineResponseMetric[];
  highlightedColumns?: Set<string>;
}) => {
  const bucketKeys = useMemo(() => bucketOrder.map((bucket) => bucket.key).filter((key) => key !== 'check'), [bucketOrder]);
  const dataColumns = useMemo(() => ['check', ...bucketKeys], [bucketKeys]);
  const columnLabels = useMemo(() => {
    const map = new Map<string, string>();
    map.set('check', 'Check');
    bucketOrder.forEach((bucket) => {
      map.set(bucket.key, bucket.label);
    });
    return map;
  }, [bucketOrder]);

  const metricMap = useMemo(() => {
    const map = new Map<string, LineResponseMetric>();
    metrics.forEach((metric) => map.set(metric.bucket_key, metric));
    return map;
  }, [metrics]);

  const maxEvents = useMemo(
    () => dataColumns.reduce((max, key) => Math.max(max, metricMap.get(key)?.events ?? 0), 0),
    [dataColumns, metricMap],
  );

  const columnMax = useMemo(() => {
    const result: Record<string, number> = {};
    dataColumns.forEach((key) => {
      const metric = metricMap.get(key);
      if (!metric) {
        result[key] = 0;
        return;
      }
      result[key] = Math.max(metric.fold_pct, metric.call_pct, metric.raise_pct, metric.continue_pct);
    });
    return result;
  }, [dataColumns, metricMap]);

  const makeRange = (selector: (metric: LineResponseMetric) => number) => {
    let min = Number.POSITIVE_INFINITY;
    let max = 0;
    dataColumns.forEach((key) => {
      const metric = metricMap.get(key);
      if (!metric) {
        return;
      }
      const value = selector(metric);
      if (value > 0 && value < min) {
        min = value;
      }
      if (value > max) {
        max = value;
      }
    });
    if (!Number.isFinite(min)) {
      min = 0;
    }
    return { min, max };
  };

  const ratioRange = makeRange((metric) => metric.avg_ratio);
  const betRange = makeRange((metric) => metric.avg_bet_bb);
  const flopAddedRange = makeRange((metric) => metric.avg_added_flop_bb);
  const allAddedRange = makeRange((metric) => metric.avg_added_all_bb);
  const shareRange = makeRange((metric) => metric.avg_share_all);

  const outlineColor = 'rgba(128, 90, 213, 0.65)';
  const isHighlighted = (key: string) => highlightedColumns?.has(key) ?? false;
  const headerHighlightProps = (key: string) => (isHighlighted(key) ? { color: 'purple.200', fontWeight: 'semibold' } : {});
  const columnOutlineProps = (key: string, { top = false, bottom = false }: { top?: boolean; bottom?: boolean }) =>
    isHighlighted(key)
      ? {
          borderLeft: `2px solid ${outlineColor}`,
          borderRight: `2px solid ${outlineColor}`,
          ...(top
            ? {
                borderTop: `2px solid ${outlineColor}`,
                borderTopLeftRadius: 'md',
                borderTopRightRadius: 'md',
              }
            : {}),
          ...(bottom
            ? {
                borderBottom: `2px solid ${outlineColor}`,
                borderBottomLeftRadius: 'md',
                borderBottomRightRadius: 'md',
              }
            : {}),
          position: 'relative' as const,
          zIndex: 1,
        }
      : {};

  const percentRows = [
    { key: 'fold_pct', label: 'Fold %', selector: (metric: LineResponseMetric) => metric.fold_pct },
    { key: 'call_pct', label: 'Call %', selector: (metric: LineResponseMetric) => metric.call_pct },
    { key: 'raise_pct', label: 'Raise %', selector: (metric: LineResponseMetric) => metric.raise_pct },
    { key: 'continue_pct', label: 'Continue %', selector: (metric: LineResponseMetric) => metric.continue_pct },
  ];

  const metricRows = [
    { key: 'avg_ratio', label: 'Avg Turn Bet (Pot Ratio)', selector: (metric: LineResponseMetric) => metric.avg_ratio, range: ratioRange, palette: 'orange' as const },
    { key: 'avg_bet_bb', label: 'Avg Turn Bet (BB)', selector: (metric: LineResponseMetric) => metric.avg_bet_bb, range: betRange, palette: 'orange' as const },
    { key: 'avg_added_flop_bb', label: 'Avg Added Pot (Flop, BB)', selector: (metric: LineResponseMetric) => metric.avg_added_flop_bb, range: flopAddedRange, palette: 'orange' as const },
    { key: 'avg_added_all_bb', label: 'Avg Added Pot (All Streets, BB)', selector: (metric: LineResponseMetric) => metric.avg_added_all_bb, range: allAddedRange, palette: 'orange' as const },
    { key: 'avg_share_all', label: 'Avg Final Pot Share', selector: (metric: LineResponseMetric) => metric.avg_share_all, range: shareRange, palette: 'red' as const },
  ];

  const totalRows = 1 + percentRows.length + metricRows.length;
  const lastRowIndex = totalRows - 1;

  const eventRow = (
    <Tr key="event-count">
      <Th scope="row">Event Count</Th>
      {dataColumns.map((key) => {
        const value = metricMap.get(key)?.events ?? 0;
        const { bg, color } = deriveCountColor(value, maxEvents);
        const props = columnOutlineProps(key, { top: true, bottom: totalRows === 1 });
        return (
          <Td key={`response-events-${key}`} isNumeric fontWeight="semibold" bg={bg} color={color} {...props}>
            {value.toLocaleString()}
          </Td>
        );
      })}
    </Tr>
  );

  let currentRowIndex = 1;
  const percentRowElements = percentRows.map((row, index) => {
    const rowIndex = currentRowIndex + index;
    const bottom = rowIndex === lastRowIndex && metricRows.length === 0;
    return (
      <Tr key={row.key}>
        <Th scope="row">{row.label}</Th>
        {dataColumns.map((key) => {
          const metric = metricMap.get(key);
          const value = metric ? row.selector(metric) : 0;
          const { bg, color } = derivePercentColor(value, columnMax[key] ?? 0);
          const props = columnOutlineProps(key, { bottom });
          const display = key === 'check' ? '—' : metric ? `${value.toFixed(1)}%` : '—';
          return (
            <Td key={`${row.key}-${key}`} isNumeric bg={bg} color={color} {...props}>
              {display}
            </Td>
          );
        })}
      </Tr>
    );
  });

  currentRowIndex += percentRows.length;
  const metricRowElements = metricRows.map((row, index) => {
    const rowIndex = currentRowIndex + index;
    const bottom = rowIndex === lastRowIndex;
    return (
      <Tr key={row.key}>
        <Th scope="row">{row.label}</Th>
        {dataColumns.map((key) => {
          const metric = metricMap.get(key);
          const value = metric ? row.selector(metric) : 0;
          const { bg, color } = deriveRowGradient(value, row.range.max, row.palette, row.range.min);
          const props = columnOutlineProps(key, { bottom });
          const display = key === 'check' ? '—' : metric ? value.toFixed(2) : '—';
          return (
            <Td key={`${row.key}-${key}`} isNumeric bg={bg} color={color} {...props}>
              {display}
            </Td>
          );
        })}
      </Tr>
    );
  });

  return (
    <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" overflowX="auto">
      <Table size="sm" variant="unstyled">
        <Thead>
          <Tr>
            <Th rowSpan={2} textAlign="left" borderBottom="1px solid" borderColor="whiteAlpha.300" width="220px">
              Metric
            </Th>
            <Th colSpan={dataColumns.length} textAlign="center" borderBottom="1px solid" borderColor="whiteAlpha.300">
              Action
            </Th>
          </Tr>
          <Tr>
            {dataColumns.map((key) => {
              const props = {
                ...headerHighlightProps(key),
                ...columnOutlineProps(key, { top: true }),
              };
              return (
                <Th key={key} textAlign="right" borderBottom="1px solid" borderColor="whiteAlpha.300" {...props}>
                  {columnLabels.get(key) ?? key}
                </Th>
              );
            })}
          </Tr>
        </Thead>
        <Tbody>
          {eventRow}
          {percentRowElements}
          {metricRowElements}
        </Tbody>
      </Table>
    </Box>
  );
};

const HandBreakdownTable = ({
  bucketOrder,
  metrics,
  highlightedColumns,
  groupedView,
}: {
  bucketOrder: LineBucketMeta[];
  metrics: LineHandMetric[];
  highlightedColumns?: Set<string>;
  groupedView: boolean;
}) => {
  const bucketKeys = useMemo(
    () => bucketOrder.map((bucket) => bucket.key).filter((key) => key !== 'check'),
    [bucketOrder],
  );
  const dataColumns = useMemo(() => ['check', ...bucketKeys], [bucketKeys]);
  const columnLabels = useMemo(() => {
    const map = new Map<string, string>();
    map.set('check', 'Check');
    bucketOrder.forEach((bucket) => {
      map.set(bucket.key, bucket.label);
    });
    return map;
  }, [bucketOrder]);

  const metricMap = useMemo(() => {
    const map = new Map<string, LineHandMetric>();
    metrics.forEach((metric) => map.set(metric.bucket_key, metric));
    return map;
  }, [metrics]);

  const maxEvents = useMemo(
    () => dataColumns.reduce((max, key) => Math.max(max, metricMap.get(key)?.events ?? 0), 0),
    [dataColumns, metricMap],
  );

  const definitions = groupedView ? HAND_GROUP_DEFINITIONS : HAND_TYPE_DEFINITIONS;

  const { rows, columnMax } = useMemo(() => {
    const resultColumnMax: Record<string, number> = {};
    dataColumns.forEach((key) => {
      resultColumnMax[key] = 0;
    });

    const computedRows = definitions.map((definition) => {
      const values = dataColumns.map((key) => {
        const metric = metricMap.get(key);
        const events = metric?.events ?? 0;
        const count = definition.members.reduce((total, member) => total + (metric?.categories?.[member] ?? 0), 0);
        const percent = events > 0 ? (count / events) * 100 : 0;
        resultColumnMax[key] = Math.max(resultColumnMax[key], percent);
        return { bucketKey: key, events, count, percent };
      });
      return { key: definition.key, label: definition.label, values };
    });

    return { rows: computedRows, columnMax: resultColumnMax };
  }, [dataColumns, definitions, metricMap]);

  const outlineColor = 'rgba(128, 90, 213, 0.65)';
  const isHighlighted = (key: string) => highlightedColumns?.has(key) ?? false;
  const headerHighlightProps = (key: string) => (isHighlighted(key) ? { color: 'purple.200', fontWeight: 'semibold' } : {});
  const columnOutlineProps = (key: string, { top = false, bottom = false }: { top?: boolean; bottom?: boolean }) =>
    isHighlighted(key)
      ? {
          borderLeft: `2px solid ${outlineColor}`,
          borderRight: `2px solid ${outlineColor}`,
          ...(top
            ? {
                borderTop: `2px solid ${outlineColor}`,
                borderTopLeftRadius: 'md',
                borderTopRightRadius: 'md',
              }
            : {}),
          ...(bottom
            ? {
                borderBottom: `2px solid ${outlineColor}`,
                borderBottomLeftRadius: 'md',
                borderBottomRightRadius: 'md',
              }
            : {}),
          position: 'relative' as const,
          zIndex: 1,
        }
      : {};

  const totalRows = rows.length + 1;
  const lastRowIndex = totalRows - 1;

  const eventRow = (
    <Tr key="hand-events">
      <Th scope="row">Event Count</Th>
      {dataColumns.map((key) => {
        const value = metricMap.get(key)?.events ?? 0;
        const { bg, color } = deriveCountColor(value, maxEvents);
        const props = columnOutlineProps(key, { top: true, bottom: rows.length === 0 });
        return (
          <Td key={`hand-events-${key}`} isNumeric fontWeight="semibold" bg={bg} color={color} {...props}>
            {value.toLocaleString()}
          </Td>
        );
      })}
    </Tr>
  );

  const categoryRows = rows.map((row, index) => {
    const rowIndex = index + 1;
    const bottom = rowIndex === lastRowIndex;
    return (
      <Tr key={row.key}>
        <Th scope="row">{row.label}</Th>
        {row.values.map((value) => {
          const { bg, color } = derivePercentColor(value.percent, columnMax[value.bucketKey] ?? 0);
          const props = columnOutlineProps(value.bucketKey, { bottom });
          const display = value.bucketKey === 'check' ? '—' : value.events > 0 ? `${value.percent.toFixed(1)}%` : '—';
          return (
            <Td key={`${row.key}-${value.bucketKey}`} isNumeric bg={bg} color={color} {...props}>
              {display}
            </Td>
          );
        })}
      </Tr>
    );
  });

  return (
    <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" overflowX="auto">
      <Table size="sm" variant="unstyled">
        <Thead>
          <Tr>
            <Th rowSpan={2} textAlign="left" borderBottom="1px solid" borderColor="whiteAlpha.300" width="220px">
              Hand Type
            </Th>
            <Th colSpan={dataColumns.length} textAlign="center" borderBottom="1px solid" borderColor="whiteAlpha.300">
              Action
            </Th>
          </Tr>
          <Tr>
            {dataColumns.map((key) => {
              const props = {
                ...headerHighlightProps(key),
                ...columnOutlineProps(key, { top: true }),
              };
              return (
                <Th key={key} textAlign="right" borderBottom="1px solid" borderColor="whiteAlpha.300" {...props}>
                  {columnLabels.get(key) ?? key}
                </Th>
              );
            })}
          </Tr>
        </Thead>
        <Tbody>
          {eventRow}
          {categoryRows}
        </Tbody>
      </Table>
    </Box>
  );
};

export default LineExplorer;
