import {
  Box,
  Button,
  Heading,
  SimpleGrid,
  Spinner,
  Stack,
  Stat,
  StatLabel,
  StatNumber,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Text,
} from '@chakra-ui/react';
import { useMemo, useState } from 'react';
import {
  PerformanceMetrics,
  RawPerformanceMetrics,
  TimelineEntry,
  useOpponentCountPerformance,
} from '../hooks/useOpponentCountPerformance';
import { sortPositions } from '../utils/positionOrder';
import LineChart from '../components/LineChart';

const integerFormatter = new Intl.NumberFormat('en-US');
const decimalFormatter = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

type MetricKey = Exclude<keyof PerformanceMetrics, 'raw'>;

type MetricDefinition = { key: MetricKey; label: string };

const METRIC_ORDER: MetricDefinition[] = [
  { key: 'hand_count', label: 'Hand Count' },
  { key: 'net_bb', label: 'Net (bb)' },
  { key: 'net_dollars', label: 'Net ($)' },
  { key: 'bb_per_100', label: 'bb/100' },
  { key: 'vpip_pct', label: 'VPIP %' },
  { key: 'pfr_pct', label: 'PFR %' },
  { key: 'three_bet_pct', label: '3-Bet %' },
  { key: 'avg_pot_bb', label: 'Average Pot (bb)' },
];

const emptyRaw = (): RawPerformanceMetrics => ({
  hand_count: 0,
  net_cents: 0,
  net_bb: 0,
  vpip_hands: 0,
  pfr_hands: 0,
  three_bet_hands: 0,
  three_bet_opportunities: 0,
  pot_bb_sum: 0,
  pot_samples: 0,
});

const mergeRaw = (base: RawPerformanceMetrics, addition: RawPerformanceMetrics): RawPerformanceMetrics => ({
  hand_count: base.hand_count + addition.hand_count,
  net_cents: base.net_cents + addition.net_cents,
  net_bb: base.net_bb + addition.net_bb,
  vpip_hands: base.vpip_hands + addition.vpip_hands,
  pfr_hands: base.pfr_hands + addition.pfr_hands,
  three_bet_hands: base.three_bet_hands + addition.three_bet_hands,
  three_bet_opportunities: base.three_bet_opportunities + addition.three_bet_opportunities,
  pot_bb_sum: base.pot_bb_sum + addition.pot_bb_sum,
  pot_samples: base.pot_samples + addition.pot_samples,
});

const computeMetrics = (raw: RawPerformanceMetrics): PerformanceMetrics => {
  const { hand_count, net_cents, net_bb, vpip_hands, pfr_hands, three_bet_hands, three_bet_opportunities, pot_bb_sum, pot_samples } = raw;
  const net_dollars = net_cents / 100;
  const bb_per_100 = hand_count ? (net_bb / hand_count) * 100 : 0;
  const vpip_pct = hand_count ? (vpip_hands / hand_count) * 100 : 0;
  const pfr_pct = hand_count ? (pfr_hands / hand_count) * 100 : 0;
  const three_bet_pct = three_bet_opportunities ? (three_bet_hands / three_bet_opportunities) * 100 : 0;
  const avg_pot_bb = pot_samples ? pot_bb_sum / pot_samples : 0;

  return {
    hand_count,
    net_bb: Number(net_bb.toFixed(2)),
    net_dollars: Number(net_dollars.toFixed(2)),
    bb_per_100: Number(bb_per_100.toFixed(2)),
    vpip_pct: Number(vpip_pct.toFixed(2)),
    pfr_pct: Number(pfr_pct.toFixed(2)),
    three_bet_pct: Number(three_bet_pct.toFixed(2)),
    avg_pot_bb: Number(avg_pot_bb.toFixed(2)),
    raw,
  };
};

const formatMetricValue = (key: MetricKey, value: number): string => {
  switch (key) {
    case 'hand_count':
      return integerFormatter.format(value);
    case 'net_dollars':
      return currencyFormatter.format(value);
    case 'vpip_pct':
    case 'pfr_pct':
    case 'three_bet_pct':
      return `${decimalFormatter.format(value)}%`;
    default:
      return decimalFormatter.format(value);
  }
};

const buildSeries = (entries: TimelineEntry[], filterPosition: string | null) => {
  const filtered = filterPosition ? entries.filter((entry) => entry.position === filterPosition) : entries;
  if (filtered.length === 0) {
    return [];
  }
  const points: { x: number; y: number }[] = [];
  let cumulative = 0;
  const firstHand = filtered[0].hand_index;

  const appendPoint = (handIndex: number, value: number) => {
    points.push({ x: handIndex, y: value });
  };

  appendPoint(firstHand - 1, 0);
  const maxPoints = 1500;
  const stride = Math.max(1, Math.floor(filtered.length / maxPoints));

  filtered.forEach((entry, index) => {
    cumulative += entry.net_bb;
    if (index % stride === 0 || index === filtered.length - 1) {
      appendPoint(entry.hand_index, cumulative);
    }
  });
  return points;
};

const PerformanceOverview = () => {
  const { loading, error, data } = useOpponentCountPerformance();
  const [selectedPosition, setSelectedPosition] = useState<string | null>(null);

  const buckets = data?.buckets ?? [];
  const timeline = data?.timeline ?? [];

  const lineSeries = useMemo(() => buildSeries(timeline, selectedPosition), [timeline, selectedPosition]);

  if (loading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" minH="60vh">
        <Spinner size="xl" />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Box bg="red.600" color="white" p={6} borderRadius="md">
        <Heading size="md" mb={2}>
          Failed to load
        </Heading>
        <Text>{error ?? 'Unknown error'}.</Text>
      </Box>
    );
  }

  const overallRaw = buckets.reduce<RawPerformanceMetrics>((acc, item) => mergeRaw(acc, item.overall.raw), emptyRaw());
  const overallMetrics = computeMetrics(overallRaw);

  const positionRawMap = buckets.reduce<Record<string, RawPerformanceMetrics>>((acc, item) => {
    item.positions.forEach((position) => {
      const existing = acc[position.position] ?? emptyRaw();
      acc[position.position] = mergeRaw(existing, position.metrics.raw);
    });
    return acc;
  }, {});

  const positionMetrics = sortPositions(
    Object.entries(positionRawMap).map(([position, raw]) => ({ position, metrics: computeMetrics(raw) })),
  );

  const displayMetrics = selectedPosition ? computeMetrics(positionRawMap[selectedPosition] ?? emptyRaw()) : overallMetrics;

  const handleRowClick = (position: string) => {
    setSelectedPosition((prev) => (prev === position ? null : position));
  };

  return (
    <Stack spacing={10} py={{ base: 6, md: 10 }} px={{ base: 4, md: 8 }} maxW="1500px" mx="auto">
      <Stack spacing={3}>
        <Heading size="2xl">Performance Overview</Heading>
        <Text color="whiteAlpha.800" maxW="4xl">
          Aggregated hero performance across all opponent counts with position-level splits. Use this view for a
          single-glance summary before drilling into specific table sizes.
        </Text>
      </Stack>

      <Stack spacing={8}>
        <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" p={6} bg="blackAlpha.400">
          <Stack spacing={4}>
            <Stack direction={{ base: 'column', md: 'row' }} justify="space-between" align={{ base: 'flex-start', md: 'center' }}>
              <Heading size="lg">Overall Results</Heading>
              {selectedPosition && (
                <Button size="sm" onClick={() => setSelectedPosition(null)} colorScheme="brand" variant="outline">
                  Reset filter
                </Button>
              )}
            </Stack>
            <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} spacing={4}>
              {METRIC_ORDER.map(({ key, label }) => (
                <Stat
                  key={key}
                  bg="blackAlpha.500"
                  borderRadius="md"
                  px={4}
                  py={3}
                  borderWidth="1px"
                  borderColor={selectedPosition ? 'brand.300' : 'whiteAlpha.200'}
                >
                  <StatLabel color="whiteAlpha.700">{label}</StatLabel>
                  <StatNumber fontSize="xl">{formatMetricValue(key, displayMetrics[key])}</StatNumber>
                </Stat>
              ))}
            </SimpleGrid>

            {positionMetrics.length > 0 && (
              <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="md" overflowX="auto">
                <Box px={4} py={3} borderBottomWidth="1px" borderColor="whiteAlpha.200" bg="blackAlpha.500">
                  <Heading as="h4" size="sm" color="brand.200">
                    Breakdown by Position
                  </Heading>
                </Box>
                <Table size="sm" variant="unstyled">
                  <Thead>
                    <Tr>
                      <Th color="whiteAlpha.700" fontSize="xs" textTransform="uppercase" letterSpacing="wider">
                        Position
                      </Th>
                      {METRIC_ORDER.map(({ key, label }) => (
                        <Th key={key} color="whiteAlpha.700" fontSize="xs" textTransform="uppercase" letterSpacing="wider" textAlign="right">
                          {label}
                        </Th>
                      ))}
                    </Tr>
                  </Thead>
                  <Tbody>
                    {positionMetrics.map(({ position, metrics }) => {
                      const isSelected = selectedPosition === position;
                      return (
                        <Tr
                          key={position}
                          cursor="pointer"
                          bg={isSelected ? 'brand.200' : 'transparent'}
                          color={isSelected ? 'black' : 'inherit'}
                          _hover={{ bg: isSelected ? 'brand.200' : 'whiteAlpha.100' }}
                          onClick={() => handleRowClick(position)}
                          transition="background-color 0.15s ease"
                        >
                          <Td fontWeight="semibold">{position}</Td>
                          {METRIC_ORDER.map(({ key }) => (
                            <Td key={key} textAlign="right">
                              {formatMetricValue(key, metrics[key])}
                            </Td>
                          ))}
                        </Tr>
                      );
                    })}
                  </Tbody>
                </Table>
              </Box>
            )}
          </Stack>
        </Box>

        <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" p={6} bg="blackAlpha.400">
          <Stack spacing={4}>
            <Heading size="lg">
              Net Results Over Time {selectedPosition ? `(${selectedPosition})` : '(All Hands)'}
            </Heading>
            <LineChart points={lineSeries} highlighted={Boolean(selectedPosition)} />
          </Stack>
        </Box>
      </Stack>
    </Stack>
  );
};

export default PerformanceOverview;
