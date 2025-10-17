import { ChangeEvent, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  AlertIcon,
  Badge,
  Box,
  Button,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Select,
  SimpleGrid,
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
  ResponseCurvePoint,
  ResponseCurveScenario,
  StackBucketOption,
  PotBucketOption,
  useResponseCurves,
} from '../hooks/useResponseCurves';

const formatPercent = (value: number) => `${value.toFixed(1)}%`;
const formatBb = (value: number, digits = 2) => `${value.toFixed(digits)} bb`;
const formatPlayers = (value: number) => value.toFixed(2);
const evColor = (value: number) => (value >= 0 ? 'green.300' : 'red.300');

const sortPoints = (points: ResponseCurvePoint[]) =>
  [...points].sort((a, b) => a.representative_ratio - b.representative_ratio);

const SummaryStat = ({ label, value }: { label: string; value: string }) => (
  <Box bg="blackAlpha.500" borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="md" p={3} minH="72px">
    <Text fontSize="xs" textTransform="uppercase" color="whiteAlpha.600" letterSpacing="wide" mb={1}>
      {label}
    </Text>
    <Text fontWeight="semibold" fontSize="lg">
      {value}
    </Text>
  </Box>
);

const ScenarioCard = ({ scenario }: { scenario: ResponseCurveScenario }) => {
  const points = useMemo(() => sortPoints(scenario.points), [scenario.points]);

  return (
    <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" p={{ base: 4, md: 6 }}>
      <Stack spacing={4}>
        <Flex justify="space-between" align="flex-start" gap={3} wrap="wrap">
          <Stack spacing={1} maxW={{ base: '100%', md: '70%' }}>
            <Heading size="md">{scenario.situation_label || 'Preflop scenario'}</Heading>
            <Text fontSize="sm" color="whiteAlpha.700">
              Hero {scenario.hero_position} • {scenario.stack_depth} • {scenario.pot_bucket}
            </Text>
          </Stack>
          <Stack spacing={2} direction="row" align="center">
            <Badge colorScheme="purple" fontSize="0.8em">
              {scenario.sample_size.toLocaleString()} hands
            </Badge>
          </Stack>
        </Flex>

        <SimpleGrid columns={{ base: 1, md: 3, xl: 5 }} spacing={3}>
          <SummaryStat label="Effective Stack" value={`≈ ${formatBb(scenario.effective_stack_bb, 1)}`} />
          <SummaryStat label="Pot Before Hero" value={`≈ ${formatBb(scenario.pot_size_bb, 2)}`} />
          <SummaryStat label="Players Behind" value={`${scenario.players_behind}`} />
          <SummaryStat label="Players VPIP'd Ahead" value={`${scenario.vpip_ahead}`} />
          <SummaryStat label="Situation" value={scenario.situation_key.replace(/_/g, ' ') || '—'} />
        </SimpleGrid>

        <Box overflowX="auto">
          <Table size="sm" variant="simple" colorScheme="whiteAlpha">
            <Thead>
              <Tr>
                <Th>Bet Bucket</Th>
                <Th isNumeric>Pot Ratio</Th>
                <Th isNumeric>Fold %</Th>
                <Th isNumeric>Call %</Th>
                <Th isNumeric>Raise %</Th>
                <Th isNumeric>Hero EV (bb)</Th>
                <Th isNumeric>Final Pot (bb)</Th>
                <Th isNumeric>Players Remaining</Th>
              </Tr>
            </Thead>
            <Tbody>
              {points.map((point) => (
                <Tr key={point.bucket_key}>
                  <Td>{point.bucket_label}</Td>
                  <Td isNumeric>{point.representative_ratio.toFixed(2)}</Td>
                  <Td isNumeric>{formatPercent(point.fold_pct)}</Td>
                  <Td isNumeric>{formatPercent(point.call_pct)}</Td>
                  <Td isNumeric>{formatPercent(point.raise_pct)}</Td>
                  <Td isNumeric color={evColor(point.ev_bb)}>{point.ev_bb.toFixed(2)}</Td>
                  <Td isNumeric>{point.expected_final_pot_bb.toFixed(2)}</Td>
                  <Td isNumeric>{formatPlayers(point.expected_players_remaining)}</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Box>
      </Stack>
    </Box>
  );
};

type FilterState = {
  heroPosition: string;
  stackBucket: string;
  potBucket: string;
  vpipAhead: string;
  playersBehind: string;
};

const emptyFilters: FilterState = {
  heroPosition: '',
  stackBucket: '',
  potBucket: '',
  vpipAhead: '',
  playersBehind: '',
};

const PreflopResponseCurves = () => {
  const {
    data,
    loading,
    error,
    usingSample,
    heroPositions,
    stackBuckets,
    potBuckets,
    playersBehindOptions,
    vpipAheadOptions,
  } = useResponseCurves();

  const [filters, setFilters] = useState<FilterState>(emptyFilters);
  const [initialized, setInitialized] = useState(false);

  const defaultScenario = useMemo(() => {
    if (!data.length) {
      return null;
    }
    return [...data].sort((a, b) => b.sample_size - a.sample_size)[0];
  }, [data]);

  useEffect(() => {
    if (!initialized && defaultScenario) {
      setFilters({
        heroPosition: defaultScenario.hero_position,
        stackBucket: defaultScenario.stack_bucket_key,
        potBucket: defaultScenario.pot_bucket_key,
        vpipAhead: String(defaultScenario.vpip_ahead),
        playersBehind: String(defaultScenario.players_behind),
      });
      setInitialized(true);
    }
  }, [initialized, defaultScenario]);

  const handleSelect = (key: keyof FilterState) => (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value;
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const resetFilters = () => {
    if (defaultScenario) {
      setFilters({
        heroPosition: defaultScenario.hero_position,
        stackBucket: defaultScenario.stack_bucket_key,
        potBucket: defaultScenario.pot_bucket_key,
        vpipAhead: String(defaultScenario.vpip_ahead),
        playersBehind: String(defaultScenario.players_behind),
      });
    } else {
      setFilters(emptyFilters);
    }
  };

  const filteredScenarios = useMemo(() => {
    return data.filter((scenario) => {
      if (filters.heroPosition && scenario.hero_position !== filters.heroPosition) {
        return false;
      }
      if (filters.stackBucket && scenario.stack_bucket_key !== filters.stackBucket) {
        return false;
      }
      if (filters.potBucket && scenario.pot_bucket_key !== filters.potBucket) {
        return false;
      }
      if (filters.vpipAhead && scenario.vpip_ahead !== Number(filters.vpipAhead)) {
        return false;
      }
      if (filters.playersBehind && scenario.players_behind !== Number(filters.playersBehind)) {
        return false;
      }
      return true;
    });
  }, [data, filters]);

  const orderedScenarios = useMemo(
    () => [...filteredScenarios].sort((a, b) => b.sample_size - a.sample_size || a.id.localeCompare(b.id)),
    [filteredScenarios],
  );

  if (loading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" minH="60vh">
        <Spinner size="xl" />
      </Box>
    );
  }

  return (
    <Stack spacing={8} py={{ base: 6, md: 10 }} px={{ base: 4, md: 8 }} maxW="1500px" mx="auto">
      <Stack spacing={3}>
        <Heading size="2xl">Preflop Response Curves</Heading>
        <Text color="whiteAlpha.800" maxW="4xl">
          Model how the pool reacts to different preflop bet sizes. Pick the current situation and review the fold, call,
          and raise mix alongside the expected final pot and number of players remaining for each bet-size bucket.
        </Text>
      </Stack>

      {error && (
        <Alert status="error" variant="left-accent" borderRadius="md">
          <AlertIcon />
          <Text>Failed to load live response curves – showing cached sample data instead. ({error})</Text>
        </Alert>
      )}

      {usingSample && !error && (
        <Alert status="warning" variant="left-accent" borderRadius="md">
          <AlertIcon />
          Using bundled sample response curves until the cache is populated.
        </Alert>
      )}

      <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" p={{ base: 4, md: 6 }}>
        <Stack spacing={4}>
          <Flex justify="space-between" align={{ base: 'stretch', md: 'center' }} gap={3} wrap="wrap">
            <Heading size="md">Filters</Heading>
            <Button size="sm" variant="outline" onClick={resetFilters} disabled={!defaultScenario}>
              Reset to default
            </Button>
          </Flex>
          <SimpleGrid columns={{ base: 1, sm: 2, lg: 3, xl: 5 }} spacing={4}>
            <FormControl>
              <FormLabel color="whiteAlpha.700">Hero Position</FormLabel>
              <Select value={filters.heroPosition} onChange={handleSelect('heroPosition')} bg="blackAlpha.500">
                <option value="">All positions</option>
                {heroPositions.map((position) => (
                  <option key={position} value={position}>
                    {position}
                  </option>
                ))}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel color="whiteAlpha.700">Stack Bucket</FormLabel>
              <Select value={filters.stackBucket} onChange={handleSelect('stackBucket')} bg="blackAlpha.500">
                <option value="">All stacks</option>
                {stackBuckets.map((bucket: StackBucketOption) => (
                  <option key={bucket.key} value={bucket.key}>
                    {bucket.label}
                  </option>
                ))}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel color="whiteAlpha.700">Players VPIP'd Ahead</FormLabel>
              <Select value={filters.vpipAhead} onChange={handleSelect('vpipAhead')} bg="blackAlpha.500">
                <option value="">Any</option>
                {vpipAheadOptions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel color="whiteAlpha.700">Players Behind</FormLabel>
              <Select value={filters.playersBehind} onChange={handleSelect('playersBehind')} bg="blackAlpha.500">
                <option value="">Any</option>
                {playersBehindOptions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Select>
            </FormControl>
            <FormControl>
              <FormLabel color="whiteAlpha.700">Pot Bucket</FormLabel>
              <Select value={filters.potBucket} onChange={handleSelect('potBucket')} bg="blackAlpha.500">
                <option value="">All pots</option>
                {potBuckets.map((bucket: PotBucketOption) => (
                  <option key={bucket.key} value={bucket.key}>
                    {bucket.label}
                  </option>
                ))}
              </Select>
            </FormControl>
          </SimpleGrid>
          <Text fontSize="sm" color="whiteAlpha.700">
            Showing {orderedScenarios.length} scenario{orderedScenarios.length === 1 ? '' : 's'}.
          </Text>
        </Stack>
      </Box>

      {orderedScenarios.length === 0 ? (
        <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" p={{ base: 4, md: 6 }}>
          <Text color="whiteAlpha.700">No scenarios match this combination yet. Try widening your filters.</Text>
        </Box>
      ) : (
        <Stack spacing={6}>
          {orderedScenarios.map((scenario) => (
            <ScenarioCard scenario={scenario} key={scenario.id} />
          ))}
        </Stack>
      )}
    </Stack>
  );
};

export default PreflopResponseCurves;
