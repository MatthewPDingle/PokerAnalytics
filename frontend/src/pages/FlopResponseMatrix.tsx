import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  AlertIcon,
  Button,
  ButtonGroup,
  Box,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Select,
  Spinner,
  Stack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  Switch,
} from '@chakra-ui/react';

import {
  FlopResponseScenario,
  SelectOption,
  useFlopResponseMatrix,
} from '../hooks/useFlopResponseMatrix';
import useFlopHandMatrix from '../hooks/useFlopHandMatrix';
import useFlopResponderHandMatrix from '../hooks/useFlopResponderHandMatrix';

type TableRowKey = 'foldPct' | 'callPct' | 'raisePct' | 'continuePct';

type BucketAggregate = {
  events: number;
  foldEvents: number;
  callEvents: number;
  raiseEvents: number;
  ratioSum: number;
  addedFlopSum: number;
  addedAllSum: number;
  shareAllSum: number;
  breakevenSum: number;
};

type BucketEntry = {
  events: number;
  foldPct: number;
  callPct: number;
  raisePct: number;
  continuePct: number;
  avgRatio: number;
  avgAddedFlop: number;
  avgAddedAll: number;
  avgShareAll: number;
  avgBreakevenPct: number;
};

const formatPercent = (value: number) => `${value.toFixed(1)}%`;

const formatNumber = (value: number) => value.toFixed(2);
const formatPercentValue = (value: number) => `${(value * 100).toFixed(1)}%`;

const BUCKET_REPRESENTATIVE_RATIO: Record<string, number> = {
  pct_0_25: 0.125,
  pct_25_40: 0.325,
  pct_40_60: 0.5,
  pct_60_80: 0.7,
  pct_80_100: 0.9,
  pct_100_plus: 1.6,
  all_in: 3.5,
  one_bb: 0.67,
};

const derivePercentColor = (value: number, columnMax: number) => {
  if (columnMax <= 0 || value <= 0) {
    return { bg: 'white', color: 'gray.800' };
  }
  const intensity = Math.min(Math.max(value / columnMax, 0), 1);
  const base = { r: 66, g: 153, b: 225 }; // Chakra blue.400
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
  const base = { r: 56, g: 161, b: 105 }; // Chakra green.400
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

const ANY_OPTION: SelectOption = { key: '', label: 'Any' };

const HIDDEN_BUCKET_KEYS: string[] = ['check'];

const HAND_MEMBER_KEYS = [
  'Air',
  'Underpair',
  'Bottom Pair',
  'Middle Pair',
  'Top Pair',
  'Overpair',
  'Two Pair',
  'Trips/Set',
  'Straight',
  'Flush',
  'Full House',
  'Quads',
  'Flush Draw',
  'OESD/DG',
];

const HAND_TYPE_DEFINITIONS = [
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

const HAND_GROUP_DEFINITIONS = [
  { key: 'air', label: 'Air', members: ['Air'] },
  { key: 'weak_pair', label: 'Weak Pair', members: ['Underpair', 'Bottom Pair', 'Middle Pair'] },
  { key: 'top_pair', label: 'Top Pair', members: ['Top Pair'] },
  { key: 'overpair', label: 'Overpair', members: ['Overpair'] },
  { key: 'two_pair', label: 'Two Pair', members: ['Two Pair'] },
  { key: 'trips_set', label: 'Trips/Set', members: ['Trips/Set'] },
  { key: 'monster', label: 'Monster', members: ['Straight', 'Flush', 'Full House', 'Quads'] },
  { key: 'draw', label: 'Draw', members: ['Flush Draw', 'OESD/DG'] },
];

const combineScenarios = (scenarios: FlopResponseScenario[]) => {
  const aggregates = new Map<string, BucketAggregate>();
  scenarios.forEach((scenario) => {
    scenario.metrics.forEach((metric) => {
      const existing = aggregates.get(metric.bucketKey) ?? {
        events: 0,
        foldEvents: 0,
        callEvents: 0,
        raiseEvents: 0,
        ratioSum: 0,
        addedFlopSum: 0,
        addedAllSum: 0,
        shareAllSum: 0,
        breakevenSum: 0,
      };
      aggregates.set(metric.bucketKey, {
        events: existing.events + metric.events,
        foldEvents: existing.foldEvents + metric.foldEvents,
        callEvents: existing.callEvents + metric.callEvents,
        raiseEvents: existing.raiseEvents + metric.raiseEvents,
        ratioSum: existing.ratioSum + metric.avgRatio * metric.events,
        addedFlopSum: existing.addedFlopSum + (metric.avgAddedFlopBb ?? 0) * metric.events,
        addedAllSum: existing.addedAllSum + (metric.avgAddedAllBb ?? 0) * metric.events,
        shareAllSum: existing.shareAllSum + (metric.avgShareAll ?? 0) * metric.events,
        breakevenSum: existing.breakevenSum + (metric.avgBreakevenPct ?? 0) * metric.events,
      });
    });
  });
  return aggregates;
};

const toBucketEntries = (bucketKeys: string[], aggregates: Map<string, BucketAggregate>) => {
  const entries: Record<string, BucketEntry> = {};
  let maxEvents = 0;

  bucketKeys.forEach((key) => {
    const agg = aggregates.get(key);
    const events = agg?.events ?? 0;
    const foldPct = events ? (100 * (agg?.foldEvents ?? 0)) / events : 0;
    const callPct = events ? (100 * (agg?.callEvents ?? 0)) / events : 0;
    const raisePct = events ? (100 * (agg?.raiseEvents ?? 0)) / events : 0;
    const continuePct = callPct + raisePct;

    maxEvents = Math.max(maxEvents, events);

    entries[key] = {
      events,
      foldPct,
      callPct,
      raisePct,
      continuePct,
      avgRatio: events ? (agg?.ratioSum ?? 0) / events : 0,
      avgAddedFlop: events ? (agg?.addedFlopSum ?? 0) / events : 0,
      avgAddedAll: events ? (agg?.addedAllSum ?? 0) / events : 0,
      avgShareAll: events ? (agg?.shareAllSum ?? 0) / events : 0,
      avgBreakevenPct: events ? (agg?.breakevenSum ?? 0) / events : 0,
    };
  });

  return { entries, maxEvents };
};

const FlopResponseMatrix = () => {
  const {
    data,
    bucketOrder,
    betTypes,
    positions,
    heroPositions,
    textures,
    preflopOptions,
    loading,
    error,
    usingSample,
  } = useFlopResponseMatrix();

  const [heroPosition, setHeroPosition] = useState('');
  const [betType, setBetType] = useState('');
  const [position, setPosition] = useState('');
  const [playerCount, setPlayerCount] = useState('');
  const [texture, setTexture] = useState('any');
  const [preflopCategory, setPreflopCategory] = useState('any');
  const [groupedHandTypes, setGroupedHandTypes] = useState(true);
  const [responderGroupedHandTypes, setResponderGroupedHandTypes] = useState(true);
  const [responderResponseType, setResponderResponseType] = useState<'call' | 'raise' | 'continue'>('call');

  const {
    data: handData,
    loading: handLoading,
    error: handError,
    usingSample: handUsingSample,
  } = useFlopHandMatrix();

  const {
    data: responderData,
    loading: responderLoading,
    error: responderError,
    usingSample: responderUsingSample,
    responseTypes: responderResponseTypes,
  } = useFlopResponderHandMatrix();


  const filteredBucketOrder = useMemo(
    () => bucketOrder.filter((bucket) => !HIDDEN_BUCKET_KEYS.includes(bucket.key)),
    [bucketOrder],
  );

  const bucketKeys = useMemo(() => filteredBucketOrder.map((bucket) => bucket.key), [filteredBucketOrder]);

  const betTypeOptions = useMemo(() => [ANY_OPTION, ...betTypes], [betTypes]);
  const heroPositionOptions = useMemo(
    () => [ANY_OPTION, ...heroPositions.map((value) => ({ key: value, label: value }))],
    [heroPositions],
  );
  const positionOptions = useMemo(() => [ANY_OPTION, ...positions], [positions]);
  const textureOptions = useMemo(() => {
    if (textures.length > 0) {
      return textures;
    }
    return [
      { key: 'any', label: 'All Textures' },
      { key: 'rainbow', label: 'Rainbow Flops' },
    ];
  }, [textures]);

  const preflopOptionsWithFallback = useMemo(() => {
    if (preflopOptions.length > 0) {
      return preflopOptions;
    }
    return [
      { key: 'any', label: 'All Preflop Pots' },
      { key: 'limped', label: 'Limped Pot (No Raise)' },
      { key: 'single_raise', label: 'Single-Raise Pot' },
      { key: 'three_bet_plus', label: '3-Bet+ Pot' },
    ];
  }, [preflopOptions]);

  useEffect(() => {
    if (!textureOptions.some((option) => option.key === texture)) {
      setTexture(textureOptions[0]?.key ?? 'any');
    }
  }, [textureOptions, texture]);

  useEffect(() => {
    if (!preflopOptionsWithFallback.some((option) => option.key === preflopCategory)) {
      setPreflopCategory(preflopOptionsWithFallback[0]?.key ?? 'any');
    }
  }, [preflopOptionsWithFallback, preflopCategory]);

  const availablePlayerCounts = useMemo(() => {
    const counts = new Set<number>();
    data.forEach((scenario) => {
      if (heroPosition && scenario.heroPosition !== heroPosition) {
        return;
      }
      if (betType && scenario.betType !== betType) {
        return;
      }
      if (position && scenario.position !== position) {
        return;
      }
      const scenarioTexture = scenario.textureKey ?? 'any';
      if (texture === 'any') {
        if (scenarioTexture !== 'any') {
          return;
        }
      } else if (scenarioTexture !== texture) {
        return;
      }
      const scenarioPreflop = scenario.preflopKey ?? 'any';
      if (preflopCategory === 'any') {
        if (scenarioPreflop !== 'any') {
          return;
        }
      } else if (scenarioPreflop !== preflopCategory) {
        return;
      }
      counts.add(scenario.playerCount);
    });
    const sorted = Array.from(counts).sort((a, b) => a - b);
    return sorted;
  }, [data, heroPosition, betType, position, texture, preflopCategory]);

  useEffect(() => {
    if (!playerCount) {
      return;
    }
    const numeric = Number(playerCount);
    if (Number.isNaN(numeric) || !availablePlayerCounts.includes(numeric)) {
      setPlayerCount('');
    }
  }, [availablePlayerCounts, playerCount]);

  const playerCountOptions = useMemo(
    () => [ANY_OPTION, ...availablePlayerCounts.map((value) => ({ key: String(value), label: String(value) }))],
    [availablePlayerCounts],
  );

  const responderResponseTypeOptions = useMemo(() => {
    const base =
      responderResponseTypes && responderResponseTypes.length > 0
        ? responderResponseTypes
        : [
            { key: 'call', label: 'Call' },
            { key: 'raise', label: 'Raise' },
          ];
    const seen = new Set<string>();
    const options: SelectOption[] = [];
    base.forEach((option) => {
      if ((option.key === 'call' || option.key === 'raise') && !seen.has(option.key)) {
        seen.add(option.key);
        options.push(option);
      }
    });
    if (!seen.has('continue')) {
      options.push({ key: 'continue', label: 'Continue' });
      seen.add('continue');
    }
    return options;
  }, [responderResponseTypes]);

  const matchingScenarios = useMemo(() => {
    return data.filter((scenario) => {
      if (heroPosition && scenario.heroPosition !== heroPosition) {
        return false;
      }
      if (betType && scenario.betType !== betType) {
        return false;
      }
      if (position && scenario.position !== position) {
        return false;
      }
      if (playerCount && scenario.playerCount !== Number(playerCount)) {
        return false;
      }
      const scenarioTexture = scenario.textureKey ?? 'any';
      if (texture === 'any') {
        if (scenarioTexture !== 'any') {
          return false;
        }
      } else if (scenarioTexture !== texture) {
        return false;
      }
      const scenarioPreflop = scenario.preflopKey ?? 'any';
      if (preflopCategory === 'any') {
        if (scenarioPreflop !== 'any') {
          return false;
        }
      } else if (scenarioPreflop !== preflopCategory) {
        return false;
      }
      return true;
    });
  }, [data, heroPosition, betType, position, playerCount, texture, preflopCategory]);

  const matchingHandScenarios = useMemo(() => {
    return handData.filter((scenario) => {
      if (heroPosition && scenario.heroPosition !== heroPosition) {
        return false;
      }
      if (betType && scenario.betType !== betType) {
        return false;
      }
      if (position && scenario.position !== position) {
        return false;
      }
      if (playerCount && scenario.playerCount !== Number(playerCount)) {
        return false;
      }
      const scenarioTexture = scenario.textureKey ?? 'any';
      if (texture === 'any') {
        if (scenarioTexture !== 'any') {
          return false;
        }
      } else if (scenarioTexture !== texture) {
        return false;
      }
      const scenarioPreflop = scenario.preflopKey ?? 'any';
      if (preflopCategory === 'any') {
        if (scenarioPreflop !== 'any') {
          return false;
        }
      } else if (scenarioPreflop !== preflopCategory) {
        return false;
      }
      return true;
    });
  }, [handData, heroPosition, betType, position, playerCount, texture, preflopCategory]);

  const matchingResponderScenarios = useMemo(() => {
    return responderData.filter((scenario) => {
      if (heroPosition && scenario.heroPosition !== heroPosition) {
        return false;
      }
      if (betType && scenario.betType !== betType) {
        return false;
      }
      if (position && scenario.position !== position) {
        return false;
      }
      if (playerCount && scenario.playerCount !== Number(playerCount)) {
        return false;
      }
      if (
        responderResponseType !== 'continue' &&
        scenario.responseType !== responderResponseType
      ) {
        return false;
      }
      if (
        responderResponseType === 'continue' &&
        scenario.responseType !== 'call' &&
        scenario.responseType !== 'raise'
      ) {
        return false;
      }
      const scenarioTexture = scenario.textureKey ?? 'any';
      if (texture === 'any') {
        if (scenarioTexture !== 'any') {
          return false;
        }
      } else if (scenarioTexture !== texture) {
        return false;
      }
      const scenarioPreflop = scenario.preflopKey ?? 'any';
      if (preflopCategory === 'any') {
        if (scenarioPreflop !== 'any') {
          return false;
        }
      } else if (scenarioPreflop !== preflopCategory) {
        return false;
      }
      return true;
    });
  }, [responderData, heroPosition, betType, position, playerCount, responderResponseType, texture, preflopCategory]);

  const aggregates = useMemo(() => combineScenarios(matchingScenarios), [matchingScenarios]);
  const { entries, maxEvents } = useMemo(
    () => toBucketEntries(bucketKeys, aggregates),
    [bucketKeys, aggregates],
  );

  const responseColumnMax = useMemo(() => {
    const columnMax: Record<string, number> = {};
    bucketKeys.forEach((key) => {
      const entry = entries[key];
      if (!entry) {
        columnMax[key] = 0;
        return;
      }
      columnMax[key] = Math.max(entry.foldPct, entry.callPct, entry.raisePct, entry.continuePct);
    });
    return columnMax;
  }, [bucketKeys, entries]);


  const handAggregate = useMemo(() => {
    const template = HAND_MEMBER_KEYS.reduce<Record<string, number>>((acc, key) => {
      acc[key] = 0;
      return acc;
    }, {});

    const base: Record<string, { events: number; categories: Record<string, number> }> = {};
    bucketKeys.forEach((key) => {
      base[key] = { events: 0, categories: { ...template } };
    });

    matchingHandScenarios.forEach((scenario) => {
      scenario.metrics.forEach((metric) => {
        const bucket = base[metric.bucketKey];
        if (!bucket) {
          return;
        }
        bucket.events += metric.events;
        Object.entries(metric.categories).forEach(([category, value]) => {
          if (Object.prototype.hasOwnProperty.call(bucket.categories, category) && typeof value === 'number') {
            bucket.categories[category] += value;
          }
        });
      });
    });

    let maxEventsHand = 0;
    bucketKeys.forEach((key) => {
      const value = base[key]?.events ?? 0;
      if (value > maxEventsHand) {
        maxEventsHand = value;
      }
    });

    return { buckets: base, maxEvents: maxEventsHand };
  }, [matchingHandScenarios, bucketKeys]);

  const handRowsData = useMemo(() => {
    const definitions = groupedHandTypes ? HAND_GROUP_DEFINITIONS : HAND_TYPE_DEFINITIONS;
    const columnMax: Record<string, number> = {};

    const rows = definitions.map((definition) => {
      const values = bucketKeys.map((key) => {
        const bucket = handAggregate.buckets[key];
        const eventsCount = bucket?.events ?? 0;
        const categoryCount = definition.members.reduce((total, member) => {
          const value = bucket?.categories?.[member] ?? 0;
          return total + value;
        }, 0);
        const percent = eventsCount > 0 ? (categoryCount / eventsCount) * 100 : 0;
        columnMax[key] = Math.max(columnMax[key] ?? 0, percent);
        return { bucketKey: key, events: eventsCount, count: categoryCount, percent };
      });
      return { key: definition.key, label: definition.label, values };
    });

    return { rows, columnMax };
  }, [bucketKeys, groupedHandTypes, handAggregate]);

  const responderHandAggregate = useMemo(() => {
    const template = HAND_MEMBER_KEYS.reduce<Record<string, number>>((acc, key) => {
      acc[key] = 0;
      return acc;
    }, {});

    const base: Record<string, { events: number; categories: Record<string, number> }> = {};
    bucketKeys.forEach((key) => {
      base[key] = { events: 0, categories: { ...template } };
    });

    matchingResponderScenarios.forEach((scenario) => {
      scenario.metrics.forEach((metric) => {
        const bucket = base[metric.bucketKey];
        if (!bucket) {
          return;
        }
        bucket.events += metric.events;
        Object.entries(metric.categories).forEach(([category, value]) => {
          if (Object.prototype.hasOwnProperty.call(bucket.categories, category) && typeof value === 'number') {
            bucket.categories[category] += value;
          }
        });
      });
    });

    let maxEventsResponder = 0;
    bucketKeys.forEach((key) => {
      const value = base[key]?.events ?? 0;
      if (value > maxEventsResponder) {
        maxEventsResponder = value;
      }
    });

    return { buckets: base, maxEvents: maxEventsResponder };
  }, [bucketKeys, matchingResponderScenarios]);

  const responderHandRowsData = useMemo(() => {
    const definitions = responderGroupedHandTypes ? HAND_GROUP_DEFINITIONS : HAND_TYPE_DEFINITIONS;
    const columnMax: Record<string, number> = {};

    const rows = definitions.map((definition) => {
      const values = bucketKeys.map((key) => {
        const bucket = responderHandAggregate.buckets[key];
        const eventsCount = bucket?.events ?? 0;
        const categoryCount = definition.members.reduce((total, member) => {
          const value = bucket?.categories?.[member] ?? 0;
          return total + value;
        }, 0);
        const percent = eventsCount > 0 ? (categoryCount / eventsCount) * 100 : 0;
        columnMax[key] = Math.max(columnMax[key] ?? 0, percent);
        return { bucketKey: key, events: eventsCount, count: categoryCount, percent };
      });
      return { key: definition.key, label: definition.label, values };
    });

    return { rows, columnMax };
  }, [bucketKeys, responderGroupedHandTypes, responderHandAggregate]);

  const handHasEvents = useMemo(
    () => bucketKeys.some((key) => (handAggregate.buckets[key]?.events ?? 0) > 0),
    [bucketKeys, handAggregate],
  );

  const responderHandHasEvents = useMemo(
    () => bucketKeys.some((key) => (responderHandAggregate.buckets[key]?.events ?? 0) > 0),
    [bucketKeys, responderHandAggregate],
  );

  const hasEvents = useMemo(
    () => bucketKeys.some((key) => entries[key]?.events > 0),
    [bucketKeys, entries],
  );

  const maxAvgRatio = useMemo(
    () =>
      bucketKeys.reduce((acc, key) => {
        const ratio = entries[key]?.avgRatio ?? 0;
        return ratio > acc ? ratio : acc;
      }, 0),
    [bucketKeys, entries],
  );

  const foldValueRow = useMemo(() => {
    const values = bucketKeys.map((key) => {
      const entry = entries[key];
      const ratio = entry?.avgRatio ?? BUCKET_REPRESENTATIVE_RATIO[key] ?? 0;
      if (!entry || ratio <= 0) {
        return 0;
      }
      const foldPct = entry.foldPct;
      return (foldPct / 100) / ratio;
    });
    const max = values.reduce((acc, value) => (value > acc ? value : acc), 0);
    return { values, max };
  }, [bucketKeys, entries]);

  const foldValueRiverRow = useMemo(() => {
    const values = bucketKeys.map((key) => {
      const entry = entries[key];
      if (!entry) {
        return 0;
      }
      const ratio =
        entry.avgRatio > 0
          ? entry.avgRatio
          : BUCKET_REPRESENTATIVE_RATIO[key] ?? 0;
      if (ratio <= 0) {
        return 0;
      }
      const totalShare = (entry.avgShareAll ?? 0) + 1;
      if (totalShare <= 0) {
        return 0;
      }
      return (totalShare * (entry.foldPct / 100)) / ratio;
    });
    const max = values.reduce((acc, value) => (value > acc ? value : acc), 0);
    return { values, max };
  }, [bucketKeys, entries]);

  const breakevenRow = useMemo(() => {
    const values = bucketKeys.map((key) => {
      const entry = entries[key];
      if (!entry) {
        return 0;
      }
      const breakeven = entry.avgBreakevenPct ?? 0;
      return breakeven > 0 ? breakeven : 0;
    });
    const max = values.reduce((acc, value) => (value > acc ? value : acc), 0);
    return { values, max };
  }, [bucketKeys, entries]);

  const foldSurplusRow = useMemo(() => {
    const values = bucketKeys.map((key) => {
      const entry = entries[key];
      if (!entry) {
        return 0;
      }
      const breakeven = entry.avgBreakevenPct ?? 0;
      return entry.foldPct - breakeven;
    });
    const max = values.reduce((acc, value) => (value > acc ? value : acc), 0);
    return { values, max };
  }, [bucketKeys, entries]);

  const potShareRow = useMemo(() => {
    const values = bucketKeys.map((key) => {
      const entry = entries[key];
      if (!entry) {
        return 0;
      }
      const value = entry.avgShareAll ?? 0;
      return value > 0 ? value : 0;
    });
    const max = values.reduce((acc, value) => (value > acc ? value : acc), 0);
    const minValue = values.reduce((acc, value) => {
      if (value > 0 && value < acc) {
        return value;
      }
      return acc;
    }, Number.POSITIVE_INFINITY);
    const min = minValue === Number.POSITIVE_INFINITY ? 0 : minValue;
    return { values, max, min };
  }, [bucketKeys, entries]);


  const handleSelect = (setter: (value: string) => void) => (event: ChangeEvent<HTMLSelectElement>) => {
    setter(event.target.value);
  };

  const renderOption = (option: SelectOption) => (
    <option key={option.key || 'any'} value={option.key}>
      {option.label}
    </option>
  );

  if (
    (loading && !usingSample) ||
    (handLoading && !handUsingSample) ||
    (responderLoading && !responderUsingSample)
  ) {
    return (
      <Flex align="center" justify="center" minH="60vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  return (
    <Box as="main" px={{ base: 4, md: 8 }} py={{ base: 8, md: 12 }}>
      <Stack spacing={6} maxW="1200px" mx="auto">
        <Stack spacing={3}>
          <Heading size="lg">Flop Response Matrix</Heading>
          <Text color="whiteAlpha.800">
            Explore how the population reacts to flop bets across all players at the table. Adjust the filters to slice
            the pool by bettor position, bet classification, and table size. Percentages show villain actions relative
            to the number of bets in each sizing bucket.
          </Text>
          <Stack spacing={1} fontSize="sm" color="whiteAlpha.700">
            <Text fontWeight="semibold">Bet Type Definitions</Text>
            <Text>
              • <strong>Continuation Bet (c-bet)</strong>: preflop aggressor fires the flop.
            </Text>
            <Text>
              • <strong>Donk Bet</strong>: a non-aggressor leads into the preflop raiser before they act.
            </Text>
            <Text>
              • <strong>Stab / Other</strong>: any other flop bet (missed c-bet stabs, limped pots, etc.).
            </Text>
          </Stack>
        </Stack>

        {error && (
          <Alert status={usingSample ? 'warning' : 'error'} variant="left-accent">
            <AlertIcon />
            {error}
          </Alert>
        )}

        {handError && (
          <Alert status={handUsingSample ? 'warning' : 'error'} variant="left-accent">
            <AlertIcon />
            {handError}
          </Alert>
        )}

        {responderError && (
          <Alert status={responderUsingSample ? 'warning' : 'error'} variant="left-accent">
            <AlertIcon />
            {responderError}
          </Alert>
        )}

        <Flex gap={3} wrap="wrap">
          <FormControl flex="1 1 160px" maxW="180px">
            <FormLabel fontSize="sm">Bettor position</FormLabel>
            <Select value={heroPosition} onChange={handleSelect(setHeroPosition)}>
              {heroPositionOptions.map(renderOption)}
            </Select>
          </FormControl>
          <FormControl flex="1 1 160px" maxW="180px">
            <FormLabel fontSize="sm">Bet classification</FormLabel>
            <Select value={betType} onChange={handleSelect(setBetType)}>
              {betTypeOptions.map(renderOption)}
            </Select>
          </FormControl>
          <FormControl flex="1 1 160px" maxW="180px">
            <FormLabel fontSize="sm">Flop texture</FormLabel>
            <Select value={texture} onChange={handleSelect(setTexture)}>
              {textureOptions.map(renderOption)}
            </Select>
          </FormControl>
          <FormControl flex="1 1 160px" maxW="180px">
            <FormLabel fontSize="sm">Preflop action</FormLabel>
            <Select value={preflopCategory} onChange={handleSelect(setPreflopCategory)}>
              {preflopOptionsWithFallback.map(renderOption)}
            </Select>
          </FormControl>
          <FormControl flex="1 1 160px" maxW="180px">
            <FormLabel fontSize="sm">Players on flop</FormLabel>
            <Select value={playerCount} onChange={handleSelect(setPlayerCount)}>
              {playerCountOptions.map(renderOption)}
            </Select>
          </FormControl>
          <FormControl flex="1 1 160px" maxW="180px">
            <FormLabel fontSize="sm">Bettor IP / OOP</FormLabel>
            <Select value={position} onChange={handleSelect(setPosition)}>
              {positionOptions.map(renderOption)}
            </Select>
          </FormControl>
        </Flex>

        {!hasEvents && (
          <Alert status="info" variant="left-accent">
            <AlertIcon />
            No hands matched the selected filters yet. Try loosening the filters or rebuild the underlying cache.
          </Alert>
        )}

        <Stack spacing={3} pt={{ base: 4, md: 6 }}>
          <Flex align={{ base: 'flex-start', md: 'center' }} justify="space-between" wrap="wrap" gap={3}>
            <Heading size="md">Bettor&apos;s Hand Breakdown</Heading>
            <FormControl display="flex" alignItems="center" width="auto">
              <FormLabel htmlFor="grouped-view-toggle" mb="0" fontSize="sm">
                Grouped view
              </FormLabel>
              <Switch
                id="grouped-view-toggle"
                isChecked={groupedHandTypes}
                onChange={(event) => setGroupedHandTypes(event.target.checked)}
                colorScheme="blue"
              />
            </FormControl>
          </Flex>
        </Stack>

        {!handHasEvents && (
          <Alert status="info" variant="left-accent">
            <AlertIcon />
            No hero hands matched the selected filters yet. Adjust the filters or refresh the cache.
          </Alert>
        )}

        <Box
          borderWidth="1px"
          borderColor="whiteAlpha.200"
          borderRadius="lg"
          bg="blackAlpha.400"
          p={{ base: 3, md: 5 }}
          overflowX="auto"
        >
          <Table
            size="sm"
            variant="unstyled"
            sx={{
              'thead th': {
                fontSize: 'xs',
                textTransform: 'uppercase',
                letterSpacing: 'wider',
                color: 'whiteAlpha.800',
              },
              'thead tr:first-of-type th:first-of-type': {
                width: '240px',
              },
              'thead th:not(:last-child)': {
                borderRight: '1px solid',
                borderColor: 'whiteAlpha.300',
              },
              'tbody th': {
                textTransform: 'none',
                fontSize: 'sm',
                letterSpacing: 'normal',
                color: 'whiteAlpha.900',
                borderBottom: 'none',
                width: '240px',
              },
              'thead tr:not(:first-of-type) th': {
                minWidth: '90px',
              },
              'tbody td': {
                minWidth: '90px',
                borderBottom: 'none',
              },
              'tbody td:not(:last-child)': {
                borderRight: '1px solid',
                borderColor: 'whiteAlpha.200',
              },
            }}
          >
            <Thead>
              <Tr>
                <Th
                  rowSpan={2}
                  borderBottom="1px solid"
                  borderColor="whiteAlpha.300"
                  textAlign="left"
                >
                  Hand Strength
                </Th>
                <Th
                  colSpan={bucketKeys.length}
                  textAlign="center"
                  borderBottom="1px solid"
                  borderColor="whiteAlpha.300"
                >
                  Bet Size
                </Th>
              </Tr>
              <Tr>
                {filteredBucketOrder.map((bucket) => (
                  <Th key={`hand-${bucket.key}`} textAlign="right" borderBottom="1px solid" borderColor="whiteAlpha.300">
                    {bucket.label}
                  </Th>
                ))}
              </Tr>
            </Thead>
            <Tbody>
              <Tr>
                <Th scope="row">Event Count</Th>
                {bucketKeys.map((key) => {
                  const value = handAggregate.buckets[key]?.events ?? 0;
                  const { bg, color } = deriveCountColor(value, handAggregate.maxEvents);
                  return (
                    <Td key={`hand-events-${key}`} isNumeric fontWeight="semibold" bg={bg} color={color}>
                      {value.toLocaleString()}
                    </Td>
                  );
                })}
              </Tr>
              {handRowsData.rows.map((row) => (
                <Tr key={row.key}>
                  <Th scope="row">{row.label}</Th>
                  {row.values.map((cell) => {
                    const showColor = cell.percent > 0;
                    const { bg, color } = showColor
                      ? derivePercentColor(cell.percent, handRowsData.columnMax[cell.bucketKey] ?? 0)
                      : { bg: 'white', color: 'gray.700' };
                    return (
                      <Td key={`${row.key}-${cell.bucketKey}`} isNumeric bg={showColor ? bg : 'white'} color={showColor ? color : 'gray.700'}>
                        {formatPercent(cell.percent)}
                      </Td>
                    );
                  })}
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>

        <Heading size="md">Bet Responses</Heading>

        <Box
          borderWidth="1px"
          borderColor="whiteAlpha.200"
          borderRadius="lg"
          bg="blackAlpha.400"
          p={{ base: 3, md: 5 }}
          overflowX="auto"
        >
          <Table
            size="sm"
            variant="unstyled"
            sx={{
              'thead th': {
                fontSize: 'xs',
                textTransform: 'uppercase',
                letterSpacing: 'wider',
                color: 'whiteAlpha.800',
              },
              'thead tr:first-of-type th:first-of-type': {
                width: '240px',
              },
              'thead th:not(:last-child)': {
                borderRight: '1px solid',
                borderColor: 'whiteAlpha.300',
              },
              'tbody th': {
                textTransform: 'none',
                fontSize: 'sm',
                letterSpacing: 'normal',
                color: 'whiteAlpha.900',
                borderBottom: 'none',
                width: '240px',
              },
              'thead tr:not(:first-of-type) th': {
                minWidth: '90px',
              },
              'tbody td': {
                minWidth: '90px',
                borderBottom: 'none',
              },
              'tbody td:not(:last-child)': {
                borderRight: '1px solid',
                borderColor: 'whiteAlpha.200',
              },
            }}
          >
            <Thead>
              <Tr>
                <Th
                  rowSpan={2}
                  borderBottom="1px solid"
                  borderColor="whiteAlpha.300"
                  textAlign="left"
                >
                  Response
                </Th>
                <Th
                  colSpan={bucketKeys.length}
                  textAlign="center"
                  borderBottom="1px solid"
                  borderColor="whiteAlpha.300"
                >
                  Bet Size
                </Th>
              </Tr>
              <Tr>
                {filteredBucketOrder.map((bucket) => (
                  <Th key={bucket.key} textAlign="right" borderBottom="1px solid" borderColor="whiteAlpha.300">
                    {bucket.label}
                  </Th>
                ))}
              </Tr>
            </Thead>
            <Tbody>
              <Tr>
                <Th scope="row">Event Count</Th>
                {bucketKeys.map((key) => {
                  const value = entries[key]?.events ?? 0;
                  const { bg, color } = deriveCountColor(value, maxEvents);
                  return (
                    <Td key={`events-${key}`} isNumeric fontWeight="semibold" bg={bg} color={color}>
                      {value.toLocaleString()}
                    </Td>
                  );
                })}
              </Tr>
              <Tr>
                <Th scope="row">Avg Bet Size (% Pot)</Th>
                {bucketKeys.map((key) => {
                  const ratio = entries[key]?.avgRatio ?? 0;
                  const { bg, color } = deriveCountColor(ratio, maxAvgRatio);
                  return (
                    <Td key={`avg-ratio-${key}`} isNumeric bg={ratio > 0 ? bg : 'white'} color={ratio > 0 ? color : 'gray.700'}>
                      {formatPercentValue(ratio)}
                    </Td>
                  );
                })}
              </Tr>
              {([
                { key: 'foldPct', label: 'Fold %' },
                { key: 'callPct', label: 'Call %' },
                { key: 'raisePct', label: 'Raise %' },
                { key: 'continuePct', label: 'Continue %' },
              ] as Array<{ key: TableRowKey; label: string }>).map((row) => (
                <Tr key={row.key}>
                  <Th scope="row">{row.label}</Th>
                  {bucketKeys.map((key) => {
                    const value = entries[key]?.[row.key] ?? 0;
                    const { bg, color } = derivePercentColor(value, responseColumnMax[key] ?? 0);
                    return (
                      <Td key={`${row.key}-${key}`} isNumeric bg={value > 0 ? bg : 'white'} color={value > 0 ? color : 'gray.700'}>
                        {formatPercent(value)}
                      </Td>
                    );
                  })}
                </Tr>
              ))}
              <Tr>
                <Th scope="row">Fold Value (Flop Pot Share)</Th>
                {bucketKeys.map((key, index) => {
                  const value = foldValueRow.values[index];
                  const { bg, color } = deriveRowGradient(value, foldValueRow.max, 'red');
                  return (
                    <Td key={`fold-value-${key}`} isNumeric bg={value > 0 ? bg : 'white'} color={value > 0 ? color : 'gray.700'}>
                      {formatNumber(value)}
                    </Td>
                  );
                })}
              </Tr>
              <Tr>
                <Th scope="row">Fold Value (River Pot Share)</Th>
                {bucketKeys.map((key, index) => {
                  const value = foldValueRiverRow.values[index];
                  const { bg, color } = deriveRowGradient(value, foldValueRiverRow.max, 'red');
                  return (
                    <Td key={`fold-value-river-${key}`} isNumeric bg={value > 0 ? bg : 'white'} color={value > 0 ? color : 'gray.700'}>
                      {formatNumber(value)}
                    </Td>
                  );
                })}
              </Tr>
              <Tr>
                <Th scope="row">Breakeven Fold %</Th>
                {bucketKeys.map((key, index) => {
                  const value = breakevenRow.values[index];
                  const { bg, color } = deriveRowGradient(value, breakevenRow.max, 'red');
                  return (
                    <Td key={`breakeven-${key}`} isNumeric bg={value > 0 ? bg : 'white'} color={value > 0 ? color : 'gray.700'}>
                      {formatPercent(value)}
                    </Td>
                  );
                })}
              </Tr>
              <Tr>
                <Th scope="row">Fold Surplus</Th>
                {bucketKeys.map((key, index) => {
                  const value = foldSurplusRow.values[index];
                  const { bg, color } = deriveRowGradient(value, foldSurplusRow.max, 'red');
                  return (
                    <Td key={`fold-surplus-${key}`} isNumeric bg={value > 0 ? bg : 'white'} color={value > 0 ? color : 'gray.700'}>
                      {formatPercent(value)}
                    </Td>
                  );
                })}
              </Tr>
              <Tr>
                <Th scope="row">Avg Pot Share Added (×Pot)</Th>
                {bucketKeys.map((key, index) => {
                  const value = potShareRow.values[index];
                  const { bg, color } = deriveRowGradient(value, potShareRow.max, 'orange', potShareRow.min);
                  return (
                    <Td key={`avg-added-${key}`} isNumeric bg={value > 0 ? bg : 'white'} color={value > 0 ? color : 'gray.700'}>
                      {formatNumber(value)}
                    </Td>
                  );
                })}
              </Tr>
            </Tbody>
          </Table>
        </Box>

        <Stack spacing={1} fontSize="sm" color="whiteAlpha.700">
          <Text>
            <strong>Avg Bet Size (% Pot)</strong> - shows the average bet-to-pot ratio for each bucket expressed as a percentage of the pot at the time of the flop bet.
          </Text>
          <Text>
            <strong>Fold Value (Flop Pot Share)</strong> - multiplies the fold percentage by the average bet-to-pot ratio for each bucket, approximating how much of the flop pot you claim when opponents fold immediately.
          </Text>
          <Text>
            <strong>Fold Value (River Pot Share)</strong> - applies the same fold percentage to the average share of the eventual pot (expressed in flop-pot multiples), estimating how much of the long-run pot you lock up via immediate folds.
          </Text>
          <Text>
            <strong>Breakeven Fold %</strong> - averages the fold frequency required for each bet to break even, computed from individual bet-to-pot ratios.
          </Text>
          <Text>
            <strong>Fold Surplus</strong> - subtracts the breakeven fold rate from the observed fold rate, highlighting how much extra fold equity the bucket produces.
          </Text>
          <Text>
            <strong>Avg Pot Share Added (×Pot)</strong> - expresses the average amount added to the pot across all streets, including the flop, as multiples of the pot size immediately before the flop bet.
          </Text>
        </Stack>

        <Stack spacing={3} pt={{ base: 4, md: 6 }}>
          <Flex align={{ base: 'flex-start', md: 'center' }} justify="space-between" wrap="wrap" gap={3}>
            <Heading size="md">Responder&apos;s Hand Breakdown</Heading>
            <Flex align="center" gap={3} wrap="wrap">
              <FormControl display="flex" alignItems="center" width="auto">
                <FormLabel htmlFor="responder-grouped-toggle" mb="0" fontSize="sm">
                  Grouped view
                </FormLabel>
                <Switch
                  id="responder-grouped-toggle"
                  isChecked={responderGroupedHandTypes}
                  onChange={(event) => setResponderGroupedHandTypes(event.target.checked)}
                  colorScheme="blue"
                />
              </FormControl>
              <ButtonGroup size="sm" isAttached variant="outline">
                {responderResponseTypeOptions.map((option) => (
                  <Button
                    key={option.key}
                    onClick={() => setResponderResponseType(option.key as 'call' | 'raise' | 'continue')}
                    isActive={option.key === responderResponseType}
                  >
                    {option.label}
                  </Button>
                ))}
              </ButtonGroup>
            </Flex>
          </Flex>
        </Stack>

        {!responderHandHasEvents && (
          <Alert status="info" variant="left-accent">
            <AlertIcon />
            No responder hands matched the selected filters yet. Adjust the filters or refresh the cache.
          </Alert>
        )}

        <Box
          borderWidth="1px"
          borderColor="whiteAlpha.200"
          borderRadius="lg"
          bg="blackAlpha.400"
          p={{ base: 3, md: 5 }}
          overflowX="auto"
        >
          <Table
            size="sm"
            variant="unstyled"
            sx={{
              'thead th': {
                fontSize: 'xs',
                textTransform: 'uppercase',
                letterSpacing: 'wider',
                color: 'whiteAlpha.800',
              },
              'thead tr:first-of-type th:first-of-type': {
                width: '240px',
              },
              'thead th:not(:last-child)': {
                borderRight: '1px solid',
                borderColor: 'whiteAlpha.300',
              },
              'tbody th': {
                textTransform: 'none',
                fontSize: 'sm',
                letterSpacing: 'normal',
                color: 'whiteAlpha.900',
                borderBottom: 'none',
                width: '240px',
              },
              'thead tr:not(:first-of-type) th': {
                minWidth: '90px',
              },
              'tbody td': {
                minWidth: '90px',
                borderBottom: 'none',
              },
              'tbody td:not(:last-child)': {
                borderRight: '1px solid',
                borderColor: 'whiteAlpha.200',
              },
            }}
          >
            <Thead>
              <Tr>
                <Th
                  rowSpan={2}
                  borderBottom="1px solid"
                  borderColor="whiteAlpha.300"
                  textAlign="left"
                >
                  Hand Strength
                </Th>
                <Th
                  colSpan={bucketKeys.length}
                  textAlign="center"
                  borderBottom="1px solid"
                  borderColor="whiteAlpha.300"
                >
                  Bet Size
                </Th>
              </Tr>
              <Tr>
                {filteredBucketOrder.map((bucket) => (
                  <Th key={`responder-${bucket.key}`} textAlign="right" borderBottom="1px solid" borderColor="whiteAlpha.300">
                    {bucket.label}
                  </Th>
                ))}
              </Tr>
            </Thead>
            <Tbody>
              <Tr>
                <Th scope="row">Event Count</Th>
                {bucketKeys.map((key) => {
                  const value = responderHandAggregate.buckets[key]?.events ?? 0;
                  const { bg, color } = deriveCountColor(value, responderHandAggregate.maxEvents);
                  return (
                    <Td key={`responder-events-${key}`} isNumeric fontWeight="semibold" bg={bg} color={color}>
                      {value.toLocaleString()}
                    </Td>
                  );
                })}
              </Tr>
              {responderHandRowsData.rows.map((row) => (
                <Tr key={row.key}>
                  <Th scope="row">{row.label}</Th>
                  {row.values.map((cell) => {
                    const showColor = cell.percent > 0;
                    const { bg, color } = showColor
                      ? derivePercentColor(cell.percent, responderHandRowsData.columnMax[cell.bucketKey] ?? 0)
                      : { bg: 'white', color: 'gray.700' };
                    return (
                      <Td
                        key={`${row.key}-${cell.bucketKey}`}
                        isNumeric
                        bg={showColor ? bg : 'white'}
                        color={showColor ? color : 'gray.700'}
                      >
                        {formatPercent(cell.percent)}
                      </Td>
                    );
                  })}
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      </Stack>
    </Box>
  );
};

export default FlopResponseMatrix;
