import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  AlertIcon,
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
} from '@chakra-ui/react';

import {
  FlopResponseScenario,
  SelectOption,
  useFlopResponseMatrix,
} from '../hooks/useFlopResponseMatrix';

type TableRowKey = 'foldPct' | 'callPct' | 'raisePct' | 'continuePct';

type BucketAggregate = {
  events: number;
  foldEvents: number;
  callEvents: number;
  raiseEvents: number;
};

type BucketEntry = {
  events: number;
  foldPct: number;
  callPct: number;
  raisePct: number;
  continuePct: number;
};

const formatPercent = (value: number) => `${value.toFixed(1)}%`;

const derivePercentColor = (value: number, max: number) => {
  if (max <= 0 || value <= 0) {
    return { bg: 'white', color: 'gray.800' };
  }
  const intensity = Math.min(Math.max(value / max, 0), 1);
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

const ANY_OPTION: SelectOption = { key: '', label: 'Any' };

const HIDDEN_BUCKET_KEYS = ['pct_125_200', 'pct_200_300', 'pct_300_plus'];

const combineScenarios = (scenarios: FlopResponseScenario[]) => {
  const aggregates = new Map<string, BucketAggregate>();
  scenarios.forEach((scenario) => {
    scenario.metrics.forEach((metric) => {
      const existing = aggregates.get(metric.bucketKey) ?? {
        events: 0,
        foldEvents: 0,
        callEvents: 0,
        raiseEvents: 0,
      };
      aggregates.set(metric.bucketKey, {
        events: existing.events + metric.events,
        foldEvents: existing.foldEvents + metric.foldEvents,
        callEvents: existing.callEvents + metric.callEvents,
        raiseEvents: existing.raiseEvents + metric.raiseEvents,
      });
    });
  });
  return aggregates;
};

const toBucketEntries = (bucketKeys: string[], aggregates: Map<string, BucketAggregate>) => {
  const entries: Record<string, BucketEntry> = {};
  let maxPercent = 0;
  let maxEvents = 0;

  bucketKeys.forEach((key) => {
    const agg = aggregates.get(key);
    const events = agg?.events ?? 0;
    const foldPct = events ? (100 * (agg?.foldEvents ?? 0)) / events : 0;
    const callPct = events ? (100 * (agg?.callEvents ?? 0)) / events : 0;
    const raisePct = events ? (100 * (agg?.raiseEvents ?? 0)) / events : 0;
    const continuePct = callPct + raisePct;

    maxPercent = Math.max(maxPercent, foldPct, callPct, raisePct, continuePct);
    maxEvents = Math.max(maxEvents, events);

    entries[key] = {
      events,
      foldPct,
      callPct,
      raisePct,
      continuePct,
    };
  });

  return { entries, maxPercent, maxEvents };
};

const FlopResponseMatrix = () => {
  const { data, bucketOrder, betTypes, positions, heroPositions, loading, error, usingSample } =
    useFlopResponseMatrix();

  const [heroPosition, setHeroPosition] = useState('');
  const [betType, setBetType] = useState('');
  const [position, setPosition] = useState('');
  const [playerCount, setPlayerCount] = useState('');

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
      counts.add(scenario.playerCount);
    });
    const sorted = Array.from(counts).sort((a, b) => a - b);
    return sorted;
  }, [data, heroPosition, betType, position]);

  useEffect(() => {
    if (!playerCount) {
      return;
    }
    const numeric = Number(playerCount);
    if (Number.isNaN(numeric) || !availablePlayerCounts.includes(numeric)) {
      setPlayerCount('');
    }
  }, [availablePlayerCounts, playerCount]);

  const playerCountOptions = useMemo(() => [ANY_OPTION, ...availablePlayerCounts.map((value) => ({ key: String(value), label: String(value) }))], [availablePlayerCounts]);

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
      return true;
    });
  }, [data, heroPosition, betType, position, playerCount]);

  const aggregates = useMemo(() => combineScenarios(matchingScenarios), [matchingScenarios]);
  const { entries, maxPercent, maxEvents } = useMemo(
    () => toBucketEntries(bucketKeys, aggregates),
    [bucketKeys, aggregates],
  );

  const hasEvents = useMemo(
    () => bucketKeys.some((key) => entries[key]?.events > 0),
    [bucketKeys, entries],
  );

  const handleSelect = (setter: (value: string) => void) => (event: ChangeEvent<HTMLSelectElement>) => {
    setter(event.target.value);
  };

  const renderOption = (option: SelectOption) => (
    <option key={option.key || 'any'} value={option.key}>
      {option.label}
    </option>
  );

  if (loading && !usingSample) {
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
            Explore how opponents react to your flop bets. Adjust the filters to see how the pool responds across hero
            positions, bet types, and table sizes. Percentages measure villain actions relative to the event count in
            each sizing bucket.
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

        <Flex gap={4} wrap="wrap">
          <FormControl maxW="220px">
            <FormLabel fontSize="sm">Hero position</FormLabel>
            <Select value={heroPosition} onChange={handleSelect(setHeroPosition)}>
              {heroPositionOptions.map(renderOption)}
            </Select>
          </FormControl>
          <FormControl maxW="220px">
            <FormLabel fontSize="sm">Bet classification</FormLabel>
            <Select value={betType} onChange={handleSelect(setBetType)}>
              {betTypeOptions.map(renderOption)}
            </Select>
          </FormControl>
          <FormControl maxW="220px">
            <FormLabel fontSize="sm">Players on flop</FormLabel>
            <Select value={playerCount} onChange={handleSelect(setPlayerCount)}>
              {playerCountOptions.map(renderOption)}
            </Select>
          </FormControl>
          <FormControl maxW="220px">
            <FormLabel fontSize="sm">Hero IP / OOP</FormLabel>
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
              },
              'tbody td': {
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
                  Villain Response
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
                    const { bg, color } = derivePercentColor(value, maxPercent);
                    return (
                      <Td key={`${row.key}-${key}`} isNumeric bg={value > 0 ? bg : 'white'} color={value > 0 ? color : 'gray.700'}>
                        {formatPercent(value)}
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
