import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Divider,
  Flex,
  HStack,
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
import useLineQuery, { LineActionSummary, LineBucketMeta, LineResponderSeatSummary } from '../hooks/useLineQuery';
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

const normalizeBucketKey = (key: string | null | undefined): string | null => {
  if (!key) {
    return null;
  }
  return LEGACY_BUCKET_KEY_MAP[key] ?? key;
};

const NORMALIZED_BUCKET_LABEL_LOOKUP = new Map<string, string>(
  NORMALIZED_BUCKETS.map((bucket) => [bucket.key, bucket.label] as const),
);

const normalizeBucketOrder = (input: LineBucketMeta[]): LineBucketMeta[] => {
  const normalized: LineBucketMeta[] = [];
  const seen = new Set<string>();

  NORMALIZED_BUCKETS.forEach((bucket) => {
    normalized.push({ ...bucket });
    seen.add(bucket.key);
  });

  input.forEach((bucket) => {
    const normalizedKey = normalizeBucketKey(bucket.key);
    if (!normalizedKey || seen.has(normalizedKey)) {
      return;
    }
    seen.add(normalizedKey);
    const label = NORMALIZED_BUCKET_LABEL_LOOKUP.get(normalizedKey) ?? bucket.label;
    normalized.push({ key: normalizedKey, label });
  });

  return normalized;
};

const NORMALIZED_TO_SOURCE_KEYS: Record<string, string[]> = {
  check: ['check'],
  pct_0_25: ['pct_0_25'],
  pct_25_40: ['pct_25_40'],
  pct_40_60: ['pct_40_60'],
  pct_60_80: ['pct_60_80'],
  pct_80_100: ['pct_80_100'],
  pct_100_plus: ['pct_100_plus', 'pct_125_plus', 'pct_100_125', 'pct_125_200', 'pct_200_300', 'pct_300_plus', 'pct_125_150', 'pct_150_200', 'pct_300_400'],
  one_bb: ['one_bb'],
  all_in: ['all_in'],
};

const RESPONDER_ACTION_KEYS = ['check', 'bet', 'call', 'raise', 'fold'] as const;

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
  { key: 'unknown', label: 'Unknown', members: ['Unknown'] },
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
  { key: 'unknown', label: 'Unknown', members: ['Unknown'] },
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

const BUCKET_LABEL_TO_KEY: Record<string, string> = {
  Check: 'check',
  '0-25%': 'pct_0_25',
  '0-25% Pot': 'pct_0_25',
  '25-40%': 'pct_25_40',
  '25-40% Pot': 'pct_25_40',
  '40-60%': 'pct_40_60',
  '40-60% Pot': 'pct_40_60',
  '60-80%': 'pct_60_80',
  '60-80% Pot': 'pct_60_80',
  '80-100%': 'pct_80_100',
  '80-100% Pot': 'pct_80_100',
  '100%+': 'pct_100_plus',
  '100%+ Pot': 'pct_100_plus',
  '100-125%': 'pct_100_plus',
  '100-125% Pot': 'pct_100_plus',
  '125-200%': 'pct_100_plus',
  '125-200% Pot': 'pct_100_plus',
  '200-300%': 'pct_100_plus',
  '200-300% Pot': 'pct_100_plus',
  '300%+': 'pct_100_plus',
  '300%+ Pot': 'pct_100_plus',
  '125%+': 'pct_100_plus',
  '125%+ Pot': 'pct_100_plus',
};

const NORMALIZED_BUCKET_KEY_SET = new Set(NORMALIZED_BUCKETS.map((bucket) => bucket.key));

const POT_ODDS_DISPLAY = {
  preflop: 'Preflop',
  flop: 'Flop',
  turn: 'Turn',
  river: 'River',
} as const;

const bucketSources = (key: string) => NORMALIZED_TO_SOURCE_KEYS[key] ?? [key];

const parseHighlightFilters = (context: HighlightContextSummary | null): DerivedFilterParseResult => {
  const highlightedColumns = new Set<string>();

  if (!context) {
    return { filters: {}, highlightedColumns };
  }

  const activeIds = new Set(context.activeFilterIds ?? []);
  const isActive = (id?: string) => !id || activeIds.has(id);

  const bucketKeys = new Set<string>();
  const preflopBucketKeys = new Set<string>();
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

  const recordBucketFilter = (bucketKey: string | undefined, categoryKey: string) => {
    const normalizedKey = normalizeBucketKey(bucketKey);
    if (!normalizedKey) {
      return null;
    }
    if (categoryKey === 'preflop') {
      preflopBucketKeys.add(normalizedKey);
    } else {
      bucketKeys.add(normalizedKey);
    }
    return normalizedKey;
  };

  const betBucketKey = normalizeBucketKey(context.bet?.bucketKey);
  if (betBucketKey && isActive(context.bet?.filterId)) {
    bucketKeys.add(betBucketKey);
    highlightedColumns.add(betBucketKey);
  }

  const facingBucketKey = normalizeBucketKey(context.facing?.bucketKey);
  if (facingBucketKey && isActive(context.facing?.filterId)) {
    bucketKeys.add(facingBucketKey);
    highlightedColumns.add(facingBucketKey);
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
        const normalizedKey = recordBucketFilter('all_in', category.key);
        if (normalizedKey && category.key === context.street) {
          highlightedColumns.add(normalizedKey);
        }
        return;
      }
      if (label.startsWith('Bet Size Bucket: ')) {
        const bucketLabel = label.slice('Bet Size Bucket: '.length).split('(')[0].trim();
        const bucketKey = BUCKET_LABEL_TO_KEY[bucketLabel];
        const normalizedKey = recordBucketFilter(bucketKey, category.key);
        if (normalizedKey && category.key === context.street) {
          highlightedColumns.add(normalizedKey);
        }
        return;
      }
      if (label.startsWith('Facing Bet Bucket: ')) {
        const bucketLabel = label.slice('Facing Bet Bucket: '.length).split('(')[0].trim();
        const bucketKey = BUCKET_LABEL_TO_KEY[bucketLabel];
        const normalizedKey = recordBucketFilter(bucketKey, category.key);
        if (normalizedKey && category.key === context.street) {
          highlightedColumns.add(normalizedKey);
        }
        return;
      }
      if (POT_ODDS_BUCKET_RANGES[label]) {
        applyRatioRange(POT_ODDS_BUCKET_RANGES[label]);
        return;
      }
      if (label.startsWith('Facing Size >= ')) {
        const threshold = parseFloat(label.slice('Facing Size >= '.length));
        if (Number.isFinite(threshold)) {
          ratioMin = ratioMin !== null ? Math.max(ratioMin, threshold / 100) : threshold / 100;
        }
        return;
      }
      if (label.startsWith('Facing Size <= ')) {
        const threshold = parseFloat(label.slice('Facing Size <= '.length));
        if (Number.isFinite(threshold)) {
          ratioMax = ratioMax !== null ? Math.min(ratioMax, threshold / 100) : threshold / 100;
        }
        return;
      }
    });
  });

  const filters: DerivedRequestFilters = {};
  if (bucketKeys.size > 0) {
    filters.bucketKeys = Array.from(bucketKeys);
  }
  if (preflopBucketKeys.size > 0) {
    filters.preflopBucketKeys = Array.from(preflopBucketKeys);
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
type DerivedRequestFilters = {
  bucketKeys?: string[];
  preflopBucketKeys?: string[];
  textureKeys?: string[];
  playersDealt?: number[];
  playerCounts?: number[];
  playersRemaining?: number[];
  heroPositions?: string[];
  relativePositions?: string[];
  effectiveStackBuckets?: string[];
  sprBuckets?: string[];
  ratioMin?: number | null;
  ratioMax?: number | null;
  minPreflopRaises?: number | null;
  allInCalled?: boolean;
  lineKeys?: string[];
};

type DerivedFilterParseResult = {
  filters: DerivedRequestFilters;
  highlightedColumns: Set<string>;
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

const deriveShareColor = (value: number, max: number) => {
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

const deriveRowGradientFromBase = (
  value: number,
  rowMax: number,
  rowMin: number,
  base: { r: number; g: number; b: number },
) => {
  if (rowMax <= rowMin) {
    return { bg: 'white', color: 'gray.800' };
  }
  const clamped = Math.min(Math.max(value, rowMin), rowMax);
  const range = rowMax - rowMin;
  const intensity = Math.min(Math.max((clamped - rowMin) / range, 0), 1);
  const r = Math.round(255 - (255 - base.r) * intensity);
  const g = Math.round(255 - (255 - base.g) * intensity);
  const b = Math.round(255 - (255 - base.b) * intensity);
  const textColor = intensity > 0.6 ? 'white' : 'gray.900';
  return { bg: `rgb(${r}, ${g}, ${b})`, color: textColor };
};

const deriveRowGradient = (value: number, rowMax: number, palette: 'orange' | 'red', rowMin = 0) => {
  const base = palette === 'orange' ? { r: 237, g: 137, b: 54 } : { r: 229, g: 62, b: 62 };
  return deriveRowGradientFromBase(value, rowMax, rowMin, base);
};

const deriveRowGradientGreen = (value: number, rowMax: number, rowMin = 0) =>
  deriveRowGradientFromBase(value, rowMax, rowMin, { r: 56, g: 161, b: 105 });

const deriveRowGradientPurple = (value: number, rowMax: number, rowMin = 0) =>
  deriveRowGradientFromBase(value, rowMax, rowMin, { r: 128, g: 90, b: 213 });

const deriveRowGradientBlue = (value: number, rowMax: number, rowMin = 0) =>
  deriveRowGradientFromBase(value, rowMax, rowMin, { r: 66, g: 153, b: 225 });
const LineExplorer = () => {
  const [composerState, dispatch] = useReducer(tableComposerReducer, undefined, () => createInitialTableComposerState());
  const [highlightContext, setHighlightContext] = useState<HighlightContextSummary | null>(null);
  const [groupedHandView, setGroupedHandView] = useState(true);
  const [showBetBuckets, setShowBetBuckets] = useState(true);
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

    if (derivedFilters.preflopBucketKeys && derivedFilters.preflopBucketKeys.length > 0) {
      combinedFilters.preflopBucketKeys = derivedFilters.preflopBucketKeys;
    } else {
      delete combinedFilters.preflopBucketKeys;
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

  const rawBucketOrder = data?.bucket_order;
  const bucketOrder = useMemo(
    () => normalizeBucketOrder(rawBucketOrder ?? DEFAULT_BUCKETS),
    [rawBucketOrder],
  );
  const actionSummaries = data?.action_summaries ?? [];
  const totalsSummary = data?.totals ?? null;

  const actionSummaryMap = useMemo(() => {
    const map = new Map<string, LineActionSummary>();
    const labelLookup = new Map<string, string>();
    bucketOrder.forEach((bucket) => labelLookup.set(bucket.key, bucket.label));

    actionSummaries.forEach((summary) => {
      if (!summary.action_key) {
        return;
      }
      const normalizedKey = normalizeBucketKey(summary.action_key);
      if (!normalizedKey) {
        return;
      }
      const label = labelLookup.get(normalizedKey) ?? summary.action_label ?? normalizedKey;
      const target = map.get(normalizedKey) ?? createEmptyActionSummary(normalizedKey, label);
      accumulateActionSummary(target, summary);
      target.action_label = label;
      map.set(normalizedKey, target);
    });

    map.forEach((summary, key) => {
      summary.action_key = key;
      summary.action_label = labelLookup.get(key) ?? summary.action_label ?? key;
      finalizeActionSummary(summary);
    });
    return map;
  }, [actionSummaries, bucketOrder]);
  const totalEvents = totalsSummary?.events ?? data?.context?.total_events ?? 0;
  const actorLabel = highlightContext?.position ?? null;

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
              <Stack spacing={4}>
                <Flex align="center" justify="space-between" wrap="wrap" gap={3}>
                  <Heading size="md">Highlighted Player Hands &amp; Actions</Heading>
                  <HStack spacing={4}>
                    <FormControl display="flex" alignItems="center" width="auto">
                      <FormLabel htmlFor="hero-hand-grouped-toggle" mb="0" fontSize="sm">
                        Group Hand Types
                      </FormLabel>
                      <Switch
                        id="hero-hand-grouped-toggle"
                        size="sm"
                        isChecked={groupedHandView}
                        onChange={(event) => setGroupedHandView(event.target.checked)}
                        colorScheme="purple"
                      />
                    </FormControl>
                    <FormControl display="flex" alignItems="center" width="auto">
                      <FormLabel htmlFor="hero-bet-bucket-toggle" mb="0" fontSize="sm">
                        Show Bet Size Buckets
                      </FormLabel>
                      <Switch
                        id="hero-bet-bucket-toggle"
                        size="sm"
                        isChecked={showBetBuckets}
                        onChange={(event) => setShowBetBuckets(event.target.checked)}
                        colorScheme="purple"
                      />
                    </FormControl>
                  </HStack>
                </Flex>
                <HeroHandMatrix
                  bucketOrder={bucketOrder}
                  summaries={actionSummaryMap}
                  totals={totalsSummary ?? undefined}
                  highlightedColumns={highlightedColumns}
                  groupedView={groupedHandView}
                  totalEvents={totalEvents}
                  actorLabel={actorLabel ?? undefined}
                  showBetBuckets={showBetBuckets}
                />
              </Stack>

              <Divider />

              <Stack spacing={4}>
                <Heading size="md">Responses to Highlighted Actions</Heading>
                <ResponderMatrix
                  bucketOrder={bucketOrder}
                  summaries={actionSummaryMap}
                  totals={totalsSummary ?? undefined}
                  highlightedColumns={highlightedColumns}
                />
              </Stack>
            </Stack>
          </Box>
        )}
      </Stack>
    </Box>
  );
};
const createEmptyResponderActionCounts = (): Record<string, number> => ({
  check: 0,
  bet: 0,
  call: 0,
  raise: 0,
  fold: 0,
});

const createEmptyActionSummary = (key: string, label: string): LineActionSummary => ({
  action_key: key,
  action_label: label,
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
  hand_categories: {},
  responder_summary: {
    total_responses: 0,
    action_counts: createEmptyResponderActionCounts(),
    hand_categories: {},
    bet_bucket_counts: {},
    seats: [],
  },
  hero_actions: {},
});

const formatPercentage = (value: number) => `${value.toFixed(1)}%`;

const mergeNumericRecord = (target: Record<string, number>, source?: Record<string, number>) => {
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

const createEmptyResponderSeatSummary = (seatLabel: string): LineResponderSeatSummary => ({
  seat_label: seatLabel,
  responses: 0,
  action_counts: createEmptyResponderActionCounts(),
  hand_categories: {},
  bet_bucket_counts: {},
  relative_positions: {},
});

const mergeSeatSummary = (target: LineResponderSeatSummary, source: LineResponderSeatSummary) => {
  target.responses += source.responses ?? 0;
  mergeNumericRecord(target.action_counts, source.action_counts);
  mergeNumericRecord(target.hand_categories, source.hand_categories);
  mergeNumericRecord(target.bet_bucket_counts, source.bet_bucket_counts);
  mergeNumericRecord(target.relative_positions, source.relative_positions);
};

const weightedAverage = (currentValue: number, currentWeight: number, nextValue: number, nextWeight: number) => {
  const totalWeight = currentWeight + nextWeight;
  if (totalWeight <= 0) {
    return 0;
  }
  const safeCurrent = Number.isFinite(currentValue) ? currentValue : 0;
  const safeNext = Number.isFinite(nextValue) ? nextValue : 0;
  return (safeCurrent * currentWeight + safeNext * nextWeight) / totalWeight;
};

const accumulateActionSummary = (target: LineActionSummary, source: LineActionSummary) => {
  const sourceEvents = source.events ?? 0;
  const priorEvents = target.events ?? 0;
  const combinedEvents = priorEvents + sourceEvents;

  target.avg_ratio = weightedAverage(target.avg_ratio ?? 0, priorEvents, source.avg_ratio ?? 0, sourceEvents);
  target.avg_bet_bb = weightedAverage(target.avg_bet_bb ?? 0, priorEvents, source.avg_bet_bb ?? 0, sourceEvents);
  target.avg_added_flop_bb = weightedAverage(
    target.avg_added_flop_bb ?? 0,
    priorEvents,
    source.avg_added_flop_bb ?? 0,
    sourceEvents,
  );
  target.avg_added_all_bb = weightedAverage(
    target.avg_added_all_bb ?? 0,
    priorEvents,
    source.avg_added_all_bb ?? 0,
    sourceEvents,
  );
  target.avg_share_all = weightedAverage(target.avg_share_all ?? 0, priorEvents, source.avg_share_all ?? 0, sourceEvents);

  target.events = combinedEvents;
  target.fold_events += source.fold_events ?? 0;
  target.call_events += source.call_events ?? 0;
  target.raise_events += source.raise_events ?? 0;
  target.continue_events += source.continue_events ?? 0;

  mergeNumericRecord(target.hand_categories, source.hand_categories);
  mergeNumericRecord(target.hero_actions, source.hero_actions);

  const targetResponder = target.responder_summary;
  const sourceResponder = source.responder_summary;
  targetResponder.total_responses += sourceResponder.total_responses ?? 0;
  mergeNumericRecord(targetResponder.action_counts, sourceResponder.action_counts);
  mergeNumericRecord(targetResponder.hand_categories, sourceResponder.hand_categories);
  mergeNumericRecord(targetResponder.bet_bucket_counts, sourceResponder.bet_bucket_counts);

  sourceResponder.seats?.forEach((seat) => {
    const existing = targetResponder.seats.find((entry) => entry.seat_label === seat.seat_label);
    if (existing) {
      mergeSeatSummary(existing, seat);
      return;
    }
    const fresh = createEmptyResponderSeatSummary(seat.seat_label);
    mergeSeatSummary(fresh, seat);
    targetResponder.seats.push(fresh);
  });
};

const finalizeActionSummary = (summary: LineActionSummary) => {
  const totalEvents = summary.events ?? 0;
  if (totalEvents > 0) {
    summary.fold_pct = (summary.fold_events / totalEvents) * 100;
    summary.call_pct = (summary.call_events / totalEvents) * 100;
    summary.raise_pct = (summary.raise_events / totalEvents) * 100;
    summary.continue_pct = (summary.continue_events / totalEvents) * 100;
  } else {
    summary.fold_pct = 0;
    summary.call_pct = 0;
    summary.raise_pct = 0;
    summary.continue_pct = 0;
  }
  return summary;
};
const buildExtendedActionSummaries = (
  bucketOrder: LineBucketMeta[],
  summaries: Map<string, LineActionSummary>,
) => {
  const nonCheckKeys = bucketOrder
    .map((bucket) => bucket.key)
    .filter((key) => key !== 'check');

  const extended = new Map<string, LineActionSummary>();
  summaries.forEach((value, key) => extended.set(key, value));

  if (nonCheckKeys.length > 0) {
    const aggregate = createEmptyActionSummary('bet_any', 'Bet (Any)');

    nonCheckKeys.forEach((key) => {
      const summary = summaries.get(key);
      if (!summary) {
        return;
      }
      aggregate.events += summary.events;
      aggregate.fold_events += summary.fold_events;
      aggregate.call_events += summary.call_events;
      aggregate.raise_events += summary.raise_events;
      aggregate.continue_events += summary.continue_events;
      Object.entries(summary.hand_categories).forEach(([handKey, count]) => {
        aggregate.hand_categories[handKey] = (aggregate.hand_categories[handKey] ?? 0) + count;
      });
      mergeNumericRecord(aggregate.hero_actions, summary.hero_actions);
      aggregate.responder_summary.total_responses += summary.responder_summary.total_responses;
      mergeNumericRecord(aggregate.responder_summary.action_counts, summary.responder_summary.action_counts);
      mergeNumericRecord(aggregate.responder_summary.hand_categories, summary.responder_summary.hand_categories);
      mergeNumericRecord(aggregate.responder_summary.bet_bucket_counts, summary.responder_summary.bet_bucket_counts);
    });

    if (aggregate.events > 0) {
      aggregate.hero_actions.bet_any = aggregate.events;
      aggregate.hero_actions.bet = (aggregate.hero_actions.bet ?? 0) + aggregate.events;
    }

    extended.set('bet_any', aggregate);
  }

  return { extended, nonCheckKeys } as const;
};

const getHandCategoryCount = (summary: LineActionSummary | undefined, definition: HandDefinition) => {
  if (!summary) {
    return 0;
  }
  return definition.members.reduce((accumulator, member) => accumulator + (summary.hand_categories?.[member] ?? 0), 0);
};
type HeroHandCell = {
  key: string;
  numerator: number;
  denominator: number;
  percent: number;
};

type HeroHandCellBase = {
  key: string;
  numerator: number;
};

type HeroHandRow = {
  key: string;
  label: string;
  events: number;
  handCells: HeroHandCell[];
  rowMaxPercent: number;
  rowMinPercent: number;
  sharePercentTotal: number;
  sharePercentBet: number;
  shareDisplayPercent: number;
  shareShading: 'green' | 'orange' | 'none';
  isBetBucket: boolean;
  isBetAggregate: boolean;
  isCheckRow: boolean;
  isAnyRow: boolean;
};

type HeroHandRowBase = {
  key: string;
  label: string;
  events: number;
  handCells: HeroHandCellBase[];
};
const HeroHandMatrix = ({
  bucketOrder,
  summaries,
  totals,
  highlightedColumns,
  groupedView,
  totalEvents,
  actorLabel,
  showBetBuckets,
}: {
  bucketOrder: LineBucketMeta[];
  summaries: Map<string, LineActionSummary>;
  totals?: LineActionSummary;
  highlightedColumns?: Set<string>;
  groupedView: boolean;
  totalEvents: number;
  actorLabel?: string;
  showBetBuckets: boolean;
}) => {
  const { extended: extendedSummaries, nonCheckKeys } = useMemo(
    () => buildExtendedActionSummaries(bucketOrder, summaries),
    [bucketOrder, summaries],
  );

  const handDefinitions = useMemo(
    () =>
      (groupedView ? HAND_GROUP_DEFINITIONS : HAND_TYPE_DEFINITIONS).filter(
        (definition) => definition.key !== 'unknown',
      ),
    [groupedView],
  );

  const actions = useMemo(() => {
    const items: Array<{ key: string; label: string }> = [{ key: 'check', label: 'Check' }];
    if (nonCheckKeys.length > 0) {
      items.push({ key: 'bet_any', label: 'Bet (Any)' });
    }
    bucketOrder.forEach((bucket) => {
      if (bucket.key === 'check') {
        return;
      }
      if (!showBetBuckets) {
        return;
      }
      items.push({ key: bucket.key, label: bucket.label });
    });
    return items;
  }, [bucketOrder, nonCheckKeys.length, showBetBuckets]);

  const actionSummaries = useMemo(() => {
    const map = new Map<string, LineActionSummary>();
    actions.forEach((action) => {
      const summary = extendedSummaries.get(action.key) ?? createEmptyActionSummary(action.key, action.label);
      map.set(action.key, summary);
    });
    return map;
  }, [actions, extendedSummaries]);

  const handTotals = useMemo(() => {
    const totalsMap = new Map<string, number>();
    const totalSummary = totals ?? null;
    handDefinitions.forEach((definition) => {
      const count = getHandCategoryCount(totalSummary ?? undefined, definition);
      totalsMap.set(definition.key, count);
    });
    return totalsMap;
  }, [handDefinitions, totals]);

  const heroTableMetrics = useMemo(() => {
    const totalSummary = totals ?? createEmptyActionSummary('total', 'Total');
    const checkSummary = actionSummaries.get('check');
    const uniqueBetEvents = Math.max(totalEvents - (checkSummary?.events ?? 0), 0);

    const betTotalsByHand = new Map<string, number>();
    handDefinitions.forEach((definition) => {
      const totalCount = getHandCategoryCount(totalSummary, definition);
      const checkCount = getHandCategoryCount(checkSummary, definition);
      betTotalsByHand.set(definition.key, Math.max(totalCount - checkCount, 0));
    });

    const baseRows: HeroHandRowBase[] = actions.map((action) => {
      const summary = actionSummaries.get(action.key) ?? createEmptyActionSummary(action.key, action.label);
      const handCells: HeroHandCellBase[] = handDefinitions.map((definition) => {
        const numerator = getHandCategoryCount(summary, definition);
        return { key: definition.key, numerator };
      });
      return {
        key: action.key,
        label: action.label,
        events: summary.events,
        handCells,
      };
    });

    let processedRows: HeroHandRow[] = baseRows.map((row) => {
      const isCheckRow = row.key === 'check';
      const isBetAggregate = row.key === 'bet_any';
      const isBetBucket = !isCheckRow && !isBetAggregate;

      let rowMaxPercent = 0;
      let rowMinPercent = Number.POSITIVE_INFINITY;

      const processedCells = row.handCells.map<HeroHandCell>((cell) => {
        const denominatorSource = isBetBucket ? betTotalsByHand : handTotals;
        const denominator = denominatorSource.get(cell.key) ?? 0;
        const percent = denominator > 0 ? (cell.numerator / denominator) * 100 : 0;
        if (percent > rowMaxPercent) {
          rowMaxPercent = percent;
        }
        if (percent < rowMinPercent) {
          rowMinPercent = percent;
        }
        return { key: cell.key, numerator: cell.numerator, denominator, percent };
      });

      if (!Number.isFinite(rowMinPercent)) {
        rowMinPercent = 0;
      }

      const sharePercentTotal = totalEvents > 0 ? (row.events / totalEvents) * 100 : 0;
      const sharePercentBet = uniqueBetEvents > 0 ? (row.events / uniqueBetEvents) * 100 : 0;

      let shareDisplayPercent = sharePercentTotal;
      let shareShading: 'green' | 'orange' | 'none' = 'none';

      if (isBetBucket) {
        shareDisplayPercent = sharePercentBet;
        shareShading = 'orange';
      } else if (isBetAggregate || isCheckRow) {
        shareShading = 'green';
      }

      return {
        key: row.key,
        label: row.label,
        events: row.events,
        handCells: processedCells,
        rowMaxPercent,
        rowMinPercent,
        sharePercentTotal,
        sharePercentBet,
        shareDisplayPercent,
        shareShading,
        isBetBucket,
        isBetAggregate,
        isCheckRow,
        isAnyRow: false,
      };
    });

    const betAnyIndex = processedRows.findIndex((row) => row.key === 'bet_any');
    if (betAnyIndex >= 0) {
      const betAnyHandCells = handDefinitions.map<HeroHandCell>((definition) => {
        const numerator = betTotalsByHand.get(definition.key) ?? 0;
        const denominator = handTotals.get(definition.key) ?? 0;
        const percent = denominator > 0 ? (numerator / denominator) * 100 : 0;
        return { key: definition.key, numerator, denominator, percent };
      });
      const betAnyRowMax = betAnyHandCells.reduce((max, cell) => Math.max(max, cell.percent), 0);
      const betAnyRowMinRaw = betAnyHandCells.reduce(
        (min, cell) => Math.min(min, cell.percent),
        Number.POSITIVE_INFINITY,
      );
      const betAnyRowMin = Number.isFinite(betAnyRowMinRaw) ? betAnyRowMinRaw : 0;
      const betAnyShare = totalEvents > 0 ? (uniqueBetEvents / totalEvents) * 100 : 0;

      processedRows[betAnyIndex] = {
        ...processedRows[betAnyIndex],
        events: uniqueBetEvents,
        handCells: betAnyHandCells,
        rowMaxPercent: betAnyRowMax,
        rowMinPercent: betAnyRowMin,
        sharePercentTotal: betAnyShare,
        sharePercentBet: betAnyShare,
        shareDisplayPercent: betAnyShare,
        shareShading: 'green',
      };
    }

    const anyRowHandCells = handDefinitions.map<HeroHandCell>((definition) => {
      const numerator = handTotals.get(definition.key) ?? 0;
      const percent = totalEvents > 0 ? (numerator / totalEvents) * 100 : 0;
      return {
        key: definition.key,
        numerator,
        denominator: totalEvents,
        percent,
      };
    });
    const anyRowMax = anyRowHandCells.reduce((max, cell) => Math.max(max, cell.percent), 0);
    const anyRowMinRaw = anyRowHandCells.reduce(
      (min, cell) => Math.min(min, cell.percent),
      Number.POSITIVE_INFINITY,
    );
    const anyRowMin = Number.isFinite(anyRowMinRaw) ? anyRowMinRaw : 0;
    const sharePercentTotalAny = totalEvents > 0 ? 100 : 0;

    const anyRow: HeroHandRow = {
      key: 'any',
      label: 'Any',
      events: totalEvents,
      handCells: anyRowHandCells,
      rowMaxPercent: anyRowMax,
      rowMinPercent: anyRowMin,
      sharePercentTotal: sharePercentTotalAny,
      sharePercentBet: 0,
      shareDisplayPercent: sharePercentTotalAny,
      shareShading: 'none',
      isBetBucket: false,
      isBetAggregate: false,
      isCheckRow: false,
      isAnyRow: true,
    };

    const rowsWithAny = [anyRow, ...processedRows];

    let purpleMax = 0;
    let shareMaxGreen = 0;
    let shareMaxOrange = 0;
    let blueMax = 0;

    rowsWithAny.forEach((row) => {
      if (row.isCheckRow || row.isBetAggregate) {
        purpleMax = Math.max(purpleMax, row.rowMaxPercent);
      }
      if (row.shareShading === 'green') {
        shareMaxGreen = Math.max(shareMaxGreen, row.sharePercentTotal);
      }
      if (row.shareShading === 'orange') {
        shareMaxOrange = Math.max(shareMaxOrange, row.sharePercentBet);
      }
      if (row.isBetBucket) {
        row.handCells.forEach((cell) => {
          blueMax = Math.max(blueMax, cell.percent);
        });
      }
    });

    return {
      rows: rowsWithAny,
      shareMaxNonBet: shareMaxGreen,
      shareMaxBet: shareMaxOrange,
      blueMax,
      purpleRowMax: purpleMax,
    };
  }, [actions, actionSummaries, handDefinitions, handTotals, totalEvents, totals, showBetBuckets]);

  const tableRows = heroTableMetrics.rows;
  const shareMaxNonBet = heroTableMetrics.shareMaxNonBet;
  const shareMaxBet = heroTableMetrics.shareMaxBet;
  const blueMax = heroTableMetrics.blueMax;
  const purpleRowMax = heroTableMetrics.purpleRowMax;

  const handColumns = handDefinitions.map((definition) => ({
    key: definition.key,
    label: definition.label,
  }));

  const isHighlighted = (actionKey: string) => highlightedColumns?.has(actionKey) ?? false;

  return (
    <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" overflowX="auto">
      <Table size="sm" variant="unstyled" sx={{ 'th, td': { fontSize: 'xs', lineHeight: 'short' } }}>
        <Thead>
          <Tr>
            <Th textAlign="left" borderBottom="1px solid" borderColor="whiteAlpha.300">
              Action
            </Th>
            <Th isNumeric borderBottom="1px solid" borderColor="whiteAlpha.300">
              Share (Events)
            </Th>
            {handColumns.map((column) => (
              <Th key={column.key} textAlign="left" borderBottom="1px solid" borderColor="whiteAlpha.300">
                {column.label}
              </Th>
            ))}
          </Tr>
        </Thead>
        <Tbody>
          {tableRows.map((row) => {
            const highlighted = isHighlighted(row.key);
            const outlineProps = highlighted
              ? { borderColor: 'purple.400', borderWidth: '1px', color: 'purple.200' }
              : { borderColor: 'whiteAlpha.200', borderWidth: '1px' };
            const fallbackColor = highlighted ? 'purple.200' : 'whiteAlpha.900';
            const shareText = `${row.events.toLocaleString()} (${formatPercentage(row.shareDisplayPercent)})`;
            const rowMax = row.rowMaxPercent || 0;
            const rowMin = row.rowMinPercent || 0;
            let shareBg = 'transparent';
            let shareColor = fallbackColor;
            if (row.shareShading === 'green') {
              const max = shareMaxNonBet > 0 ? shareMaxNonBet : row.sharePercentTotal > 0 ? row.sharePercentTotal : 1;
              const gradient = deriveShareColor(row.sharePercentTotal, max);
              shareBg = gradient.bg;
              shareColor = gradient.color;
            } else if (row.shareShading === 'orange') {
              const max = shareMaxBet > 0 ? shareMaxBet : row.sharePercentBet > 0 ? row.sharePercentBet : 1;
              const gradient = deriveRowGradient(row.sharePercentBet, max, 'orange', 0);
              shareBg = gradient.bg;
              shareColor = gradient.color;
            }
            return (
              <Tr key={row.key}>
                <Th scope="row" color={highlighted ? 'purple.200' : 'whiteAlpha.900'}>
                  {row.label}
                </Th>
                <Td isNumeric borderStyle="solid" bg={shareBg} color={shareColor} {...outlineProps}>
                  {shareText}
                </Td>
                {row.handCells.map((cell) => {
                  let cellBg = 'transparent';
                  let cellColor = fallbackColor;
                  if (row.isAnyRow) {
                    const gradient = deriveRowGradientGreen(cell.percent, rowMax || 0);
                    cellBg = gradient.bg;
                    cellColor = gradient.color;
                  } else if (row.isCheckRow || row.isBetAggregate) {
                    const gradient = deriveRowGradientPurple(cell.percent, purpleRowMax || rowMax || 0);
                    cellBg = gradient.bg;
                    cellColor = gradient.color;
                  } else if (row.isBetBucket) {
                    const gradient = deriveRowGradientBlue(cell.percent, blueMax || 0);
                    cellBg = gradient.bg;
                    cellColor = gradient.color;
                  }
                  const cellText =
                    cell.denominator > 0
                      ? `${cell.numerator.toLocaleString()} (${formatPercentage(cell.percent)})`
                      : '—';
                  return (
                    <Td
                      key={`${row.key}-${cell.key}`}
                      isNumeric
                      bg={cellBg}
                      color={cellColor}
                      borderStyle="solid"
                      {...outlineProps}
                    >
                      {cellText}
                    </Td>
                  );
                })}
              </Tr>
            );
          })}
        </Tbody>
      </Table>
      <Box mt={3} px={3} py={2} borderTop="1px solid" borderColor="whiteAlpha.200" color="whiteAlpha.700" fontSize="sm">
        {actorLabel ?? 'Selection'} actions across {totalEvents.toLocaleString()} events.
      </Box>
    </Box>
  );
};
type ResponderRow =
  | { key: 'fold' | 'call' | 'raise' | 'check'; label: string; type: 'action' }
  | { key: 'bet_any'; label: string; type: 'aggregate' }
  | { key: string; label: string; type: 'bucket' }
  | { key: 'unknown'; label: string; type: 'unknown' };

const ResponderMatrix = ({
  bucketOrder,
  summaries,
  totals,
  highlightedColumns,
}: {
  bucketOrder: LineBucketMeta[];
  summaries: Map<string, LineActionSummary>;
  totals?: LineActionSummary;
  highlightedColumns?: Set<string>;
}) => {
  const { extended: extendedSummaries, nonCheckKeys } = useMemo(
    () => buildExtendedActionSummaries(bucketOrder, summaries),
    [bucketOrder, summaries],
  );

  const columns = useMemo(() => {
    const items: Array<{ key: string; label: string }> = [{ key: 'check', label: 'Check' }];
    if (nonCheckKeys.length > 0) {
      items.push({ key: 'bet_any', label: 'Bet (Any)' });
    }
    bucketOrder.forEach((bucket) => {
      if (bucket.key === 'check') {
        return;
      }
      items.push({ key: bucket.key, label: bucket.label });
    });
    return items;
  }, [bucketOrder, nonCheckKeys.length]);

  const columnSummaries = useMemo(() => {
    const map = new Map<string, LineActionSummary>();
    columns.forEach((column) => {
      const summary = extendedSummaries.get(column.key) ?? createEmptyActionSummary(column.key, column.label);
      map.set(column.key, summary);
    });
    return map;
  }, [columns, extendedSummaries]);

  const responderRows = useMemo<ResponderRow[]>(() => {
    const base: ResponderRow[] = [
      { key: 'fold', label: 'Fold', type: 'action' },
      { key: 'call', label: 'Call', type: 'action' },
      { key: 'raise', label: 'Raise', type: 'action' },
    ];
    if (nonCheckKeys.length > 0) {
      base.push({ key: 'bet_any', label: 'Bet (Any)', type: 'aggregate' });
    }
    nonCheckKeys.forEach((key) => {
      const bucket = bucketOrder.find((entry) => entry.key === key);
      if (!bucket) {
        return;
      }
      base.push({ key, label: bucket.label, type: 'bucket' });
    });
    base.push({ key: 'check', label: 'Check', type: 'action' });
    base.push({ key: 'unknown', label: 'Unknown', type: 'unknown' });
    return base;
  }, [bucketOrder, nonCheckKeys.length]);

  const responsesByColumn = useMemo(() => {
    const counts = new Map<string, number>();
    columns.forEach((column) => {
      counts.set(column.key, columnSummaries.get(column.key)?.responder_summary.total_responses ?? 0);
    });
    return counts;
  }, [columns, columnSummaries]);

  const maxResponseCount = useMemo(() => {
    const values = Array.from(responsesByColumn.values());
    return values.length > 0 ? Math.max(...values) : 0;
  }, [responsesByColumn]);

  const getResponderCountForRow = (row: ResponderRow, summary: LineActionSummary): number => {
    const responder = summary.responder_summary;
    if (row.type === 'action') {
      return responder.action_counts[row.key] ?? 0;
    }
    if (row.type === 'aggregate') {
      return responder.action_counts.bet ?? 0;
    }
    if (row.type === 'bucket') {
      return bucketSources(row.key).reduce(
        (accumulator, sourceKey) => accumulator + (responder.bet_bucket_counts?.[sourceKey] ?? 0),
        0,
      );
    }
    const counts = responder.action_counts ?? {};
    const known =
      (counts.fold ?? 0) +
      (counts.call ?? 0) +
      (counts.raise ?? 0) +
      (counts.bet ?? 0) +
      (counts.check ?? 0);
    const remainder = responder.total_responses - known;
    return remainder > 0 ? remainder : 0;
  };

  const columnMax = useMemo(() => {
    const record: Record<string, number> = {};
    columns.forEach((column) => {
      record[column.key] = 0;
    });
    responderRows.forEach((row) => {
      columns.forEach((column) => {
        const summary = columnSummaries.get(column.key) ?? createEmptyActionSummary(column.key, column.label);
        const total = summary.responder_summary.total_responses || 0;
        const count = getResponderCountForRow(row, summary);
        const percent = total > 0 ? (count / total) * 100 : 0;
        if (percent > record[column.key]) {
          record[column.key] = percent;
        }
      });
    });
    return record;
  }, [columns, columnSummaries, responderRows]);

  const isHighlighted = (key: string) => highlightedColumns?.has(key) ?? false;
  const outlineProps = (key: string) =>
    isHighlighted(key)
      ? { borderColor: 'purple.400', borderWidth: '1px' }
      : { borderColor: 'whiteAlpha.200', borderWidth: '1px' };

  const totalResponses = useMemo(() => {
    if (totals?.responder_summary.total_responses != null) {
      return totals.responder_summary.total_responses;
    }
    const values = Array.from(responsesByColumn.values());
    return values.reduce((accumulator, value) => accumulator + value, 0);
  }, [responsesByColumn, totals]);

  return (
    <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" overflowX="auto">
      <Table size="sm" variant="unstyled" sx={{ 'th, td': { fontSize: 'xs', lineHeight: 'short' } }}>
        <Thead>
          <Tr>
            <Th textAlign="left" borderBottom="1px solid" borderColor="whiteAlpha.300">
              Responder Action
            </Th>
            {columns.map((column) => (
              <Th
                key={column.key}
                textAlign="right"
                borderBottom="1px solid"
                borderColor={isHighlighted(column.key) ? 'purple.400' : 'whiteAlpha.300'}
                color={isHighlighted(column.key) ? 'purple.200' : 'whiteAlpha.800'}
              >
                {column.label}
              </Th>
            ))}
          </Tr>
        </Thead>
        <Tbody>
          <Tr>
            <Th scope="row">Responses</Th>
            {columns.map((column) => {
              const value = responsesByColumn.get(column.key) ?? 0;
              const { bg, color } = deriveShareColor(value, maxResponseCount || 1);
              return (
                <Td key={`resp-${column.key}`} isNumeric bg={bg} color={color} borderStyle="solid" {...outlineProps(column.key)}>
                  {value.toLocaleString()}
                </Td>
              );
            })}
          </Tr>
          {responderRows.map((row) => (
            <Tr key={row.key}>
              <Th scope="row">{row.label}</Th>
              {columns.map((column) => {
                const summary = columnSummaries.get(column.key) ?? createEmptyActionSummary(column.key, column.label);
                const total = summary.responder_summary.total_responses || 0;
                const count = getResponderCountForRow(row, summary);
                const percent = total > 0 ? (count / total) * 100 : 0;
                const maxPercent = columnMax[column.key] || 100;
                const { bg, color } = derivePercentColor(percent, maxPercent);
                const cellText = total > 0 ? `${count.toLocaleString()} (${formatPercentage(percent)})` : '—';
                return (
                  <Td key={`${row.key}-${column.key}`} isNumeric bg={bg} color={color} borderStyle="solid" {...outlineProps(column.key)}>
                    {cellText}
                  </Td>
                );
              })}
            </Tr>
          ))}
        </Tbody>
      </Table>
      <Box mt={3} px={3} py={2} borderTop="1px solid" borderColor="whiteAlpha.200" color="whiteAlpha.700" fontSize="sm">
        Based on {totalResponses.toLocaleString()} behind-player responses.
      </Box>
    </Box>
  );
};

export default LineExplorer;
