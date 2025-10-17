import {
  Box,
  Flex,
  Heading,
  SimpleGrid,
  Spinner,
  Stack,
  Stat,
  StatLabel,
  StatNumber,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  Text,
} from '@chakra-ui/react';
import { useOpponentCountPerformance, PerformanceMetrics } from '../hooks/useOpponentCountPerformance';
import { sortPositions } from '../utils/positionOrder';

const integerFormatter = new Intl.NumberFormat('en-US');
const decimalFormatter = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

type MetricKey = Exclude<keyof PerformanceMetrics, 'raw'>;

const METRIC_ORDER: Array<{ key: MetricKey; label: string }> = [
  { key: 'hand_count', label: 'Hand Count' },
  { key: 'net_bb', label: 'Net (bb)' },
  { key: 'net_dollars', label: 'Net ($)' },
  { key: 'bb_per_100', label: 'bb/100' },
  { key: 'vpip_pct', label: 'VPIP %' },
  { key: 'pfr_pct', label: 'PFR %' },
  { key: 'three_bet_pct', label: '3-Bet %' },
  { key: 'avg_pot_bb', label: 'Average Pot (bb)' },
];

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

const OpponentCountPerformance = () => {
  const { loading, error, data } = useOpponentCountPerformance();
  const buckets = data?.buckets ?? [];

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

  return (
    <Stack spacing={10} py={{ base: 6, md: 10 }} px={{ base: 4, md: 8 }} maxW="1500px" mx="auto">
      <Stack spacing={3}>
        <Heading size="2xl">Performance by Opponent Count</Heading>
        <Text color="whiteAlpha.800" maxW="4xl">
          Compare win rates and preflop tendencies when multi-tabling against different numbers of opponents. Each
          block summarises overall performance plus position-level splits, with monetary results reported in big
          blinds and dollars.
        </Text>
      </Stack>

      <Stack spacing={8}>
        {buckets.map((bucket) => (
          <Box key={bucket.opponent_count} borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" p={6} bg="blackAlpha.400">
            <Stack spacing={6}>
              <Flex align="baseline" justify="space-between" wrap="wrap" gap={4}>
                <Heading size="lg">{bucket.opponent_count} Opponent{bucket.opponent_count === 1 ? '' : 's'}</Heading>
                <Text fontSize="sm" color="whiteAlpha.700">
                  {bucket.overall.hand_count.toLocaleString()} hands
                </Text>
              </Flex>

              <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} spacing={4}>
                {METRIC_ORDER.map(({ key, label }) => (
                  <Stat key={key} bg="blackAlpha.500" borderRadius="md" px={4} py={3} borderWidth="1px" borderColor="whiteAlpha.200">
                    <StatLabel color="whiteAlpha.700">{label}</StatLabel>
                    <StatNumber fontSize="xl">{formatMetricValue(key, bucket.overall[key])}</StatNumber>
                  </Stat>
                ))}
              </SimpleGrid>

              {bucket.positions.length > 0 && (
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
                      {sortPositions(bucket.positions).map((position) => (
                        <Tr key={position.position} _hover={{ bg: 'whiteAlpha.100' }}>
                          <Td fontWeight="semibold">{position.position}</Td>
                          {METRIC_ORDER.map(({ key }) => (
                            <Td key={key} textAlign="right">
                              {formatMetricValue(key, position.metrics[key])}
                            </Td>
                          ))}
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </Box>
              )}
            </Stack>
          </Box>
        ))}
      </Stack>
    </Stack>
  );
};

export default OpponentCountPerformance;
