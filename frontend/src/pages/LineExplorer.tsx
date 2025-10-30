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
import { useMemo, useReducer } from 'react';

import ActionMatrixComposer, { BucketOption } from '../components/ActionMatrixComposer';
import useLineQuery, { LineBucketMeta, LineResponseMetric, LineHandMetric } from '../hooks/useLineQuery';
import {
  createInitialTableComposerState,
  deriveDescriptorFromTable,
  tableComposerReducer,
} from '../state/tableComposer';

const DEFAULT_BUCKETS: LineBucketMeta[] = [
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

const TABLE_SIZE_OPTIONS = Array.from({ length: 9 }, (_, index) => index + 2);

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

const LineExplorer = () => {
  const [composerState, dispatch] = useReducer(tableComposerReducer, undefined, () => createInitialTableComposerState());

  const descriptorPayload = useMemo(() => deriveDescriptorFromTable(composerState), [composerState]);
  const { data, loading, error, usingSample } = useLineQuery(descriptorPayload);

  const bucketOrder = data?.bucket_order ?? DEFAULT_BUCKETS;
  const responseMetrics = data?.response_metrics ?? [];
  const handMetrics = data?.hand_metrics ?? [];
  const totalEvents = data?.context?.total_events ?? 0;

  const descriptorSteps = data?.descriptor?.steps ?? descriptorPayload.steps;
  const bucketOptions: BucketOption[] = useMemo(() => bucketOrder.map((bucket) => ({ key: bucket.key, label: bucket.label })), [bucketOrder]);

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
              <FormControl display="flex" alignItems="center" width="auto">
                <FormLabel htmlFor="exclude-hero-toggle" mb="0" fontSize="sm">
                  Exclude hero hands
                </FormLabel>
                <Switch
                  id="exclude-hero-toggle"
                  isChecked={composerState.excludeHero}
                  onChange={(event) => dispatch({ type: 'set_exclude_hero', exclude: event.target.checked })}
                  colorScheme="blue"
                />
              </FormControl>
            </Flex>
          </Flex>

          <ActionMatrixComposer state={composerState} dispatch={dispatch} bucketOptions={bucketOptions} />
        </Stack>

        {usingSample && (
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

        {loading && !data && (
          <Flex align="center" justify="center" minH="40vh">
            <Spinner size="xl" />
          </Flex>
        )}

        {data && (
          <Stack spacing={6}>
            <ContextSummary totalEvents={totalEvents} steps={descriptorSteps} excludeHero={composerState.excludeHero} />

            <Stack spacing={4}>
              <Heading size="md">Response Metrics</Heading>
              <ResponseTable bucketOrder={bucketOrder} metrics={responseMetrics} />
            </Stack>

            <Divider />

            <Stack spacing={4}>
              <Heading size="md">Responder Hand Breakdown</Heading>
              <HandBreakdownTable bucketOrder={bucketOrder} metrics={handMetrics} />
            </Stack>
          </Stack>
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

const ResponseTable = ({ bucketOrder, metrics }: { bucketOrder: LineBucketMeta[]; metrics: LineResponseMetric[] }) => {
  const bucketKeys = useMemo(() => bucketOrder.map((bucket) => bucket.key), [bucketOrder]);
  const metricMap = useMemo(() => {
    const map = new Map<string, LineResponseMetric>();
    metrics.forEach((metric) => map.set(metric.bucket_key, metric));
    return map;
  }, [metrics]);

  const maxEvents = useMemo(
    () => bucketKeys.reduce((max, key) => Math.max(max, metricMap.get(key)?.events ?? 0), 0),
    [bucketKeys, metricMap],
  );

  const columnMax = useMemo(() => {
    const map: Record<string, number> = {};
    bucketKeys.forEach((key) => {
      const metric = metricMap.get(key);
      if (!metric) {
        map[key] = 0;
        return;
      }
      map[key] = Math.max(metric.fold_pct, metric.call_pct, metric.raise_pct, metric.continue_pct);
    });
    return map;
  }, [bucketKeys, metricMap]);

  const makeRange = (selector: (metric: LineResponseMetric) => number) => {
    let min = Number.POSITIVE_INFINITY;
    let max = 0;
    bucketKeys.forEach((key) => {
      const metric = metricMap.get(key);
      if (!metric) return;
      const value = selector(metric);
      if (value > 0 && value < min) min = value;
      if (value > max) max = value;
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

  return (
    <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" overflowX="auto">
      <Table size="sm" variant="unstyled">
        <Thead>
          <Tr>
            <Th rowSpan={2} textAlign="left" borderBottom="1px solid" borderColor="whiteAlpha.300" width="220px">
              Metric
            </Th>
            <Th colSpan={bucketKeys.length} textAlign="center" borderBottom="1px solid" borderColor="whiteAlpha.300">
              Turn Bet Size
            </Th>
          </Tr>
          <Tr>
            {bucketOrder.map((bucket) => (
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
              const value = metricMap.get(key)?.events ?? 0;
              const { bg, color } = deriveCountColor(value, maxEvents);
              return (
                <Td key={`response-events-${key}`} isNumeric fontWeight="semibold" bg={bg} color={color}>
                  {value.toLocaleString()}
                </Td>
              );
            })}
          </Tr>
          {[
            { key: 'fold_pct', label: 'Fold %', selector: (metric: LineResponseMetric) => metric.fold_pct },
            { key: 'call_pct', label: 'Call %', selector: (metric: LineResponseMetric) => metric.call_pct },
            { key: 'raise_pct', label: 'Raise %', selector: (metric: LineResponseMetric) => metric.raise_pct },
            { key: 'continue_pct', label: 'Continue %', selector: (metric: LineResponseMetric) => metric.continue_pct },
          ].map((row) => (
            <Tr key={row.key}>
              <Th scope="row">{row.label}</Th>
              {bucketKeys.map((key) => {
                const metric = metricMap.get(key);
                const value = metric ? row.selector(metric) : 0;
                const { bg, color } = derivePercentColor(value, columnMax[key] ?? 0);
                return (
                  <Td key={`${row.key}-${key}`} isNumeric bg={bg} color={color}>
                    {value.toFixed(1)}%
                  </Td>
                );
              })}
            </Tr>
          ))}
          {[
            { key: 'avg_ratio', label: 'Avg Turn Bet (Pot Ratio)', selector: (metric: LineResponseMetric) => metric.avg_ratio, range: ratioRange, palette: 'orange' as const },
            { key: 'avg_bet_bb', label: 'Avg Turn Bet (BB)', selector: (metric: LineResponseMetric) => metric.avg_bet_bb, range: betRange, palette: 'orange' as const },
            { key: 'avg_added_flop_bb', label: 'Avg Added Pot (Flop, BB)', selector: (metric: LineResponseMetric) => metric.avg_added_flop_bb, range: flopAddedRange, palette: 'orange' as const },
            { key: 'avg_added_all_bb', label: 'Avg Added Pot (All Streets, BB)', selector: (metric: LineResponseMetric) => metric.avg_added_all_bb, range: allAddedRange, palette: 'orange' as const },
            { key: 'avg_share_all', label: 'Avg Final Pot Share', selector: (metric: LineResponseMetric) => metric.avg_share_all, range: shareRange, palette: 'red' as const },
          ].map((row) => (
            <Tr key={row.key}>
              <Th scope="row">{row.label}</Th>
              {bucketKeys.map((key) => {
                const metric = metricMap.get(key);
                const value = metric ? row.selector(metric) : 0;
                const { bg, color } = deriveRowGradient(value, row.range.max, row.palette, row.range.min);
                return (
                  <Td key={`${row.key}-${key}`} isNumeric bg={bg} color={color}>
                    {value.toFixed(2)}
                  </Td>
                );
              })}
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
};

const HandBreakdownTable = ({ bucketOrder, metrics }: { bucketOrder: LineBucketMeta[]; metrics: LineHandMetric[] }) => {
  const bucketKeys = useMemo(() => bucketOrder.map((bucket) => bucket.key), [bucketOrder]);
  const metricMap = useMemo(() => {
    const map = new Map<string, LineHandMetric>();
    metrics.forEach((metric) => map.set(metric.bucket_key, metric));
    return map;
  }, [metrics]);

  const rows = useMemo(() => {
    const handTypes = new Set<string>();
    metrics.forEach((metric) => {
      Object.keys(metric.categories).forEach((key) => handTypes.add(key));
    });
    return Array.from(handTypes);
  }, [metrics]);

  const maxEvents = useMemo(
    () => bucketKeys.reduce((max, key) => Math.max(max, metricMap.get(key)?.events ?? 0), 0),
    [bucketKeys, metricMap],
  );

  const columnMax = useMemo(() => {
    const map: Record<string, number> = {};
    bucketKeys.forEach((key) => {
      const metric = metricMap.get(key);
      if (!metric) {
        map[key] = 0;
        return;
      }
      const max = Math.max(
        ...rows.map((rowKey) => {
          const events = metric.events;
          const count = metric.categories[rowKey] ?? 0;
          return events > 0 ? (count / events) * 100 : 0;
        }),
      );
      map[key] = max;
    });
    return map;
  }, [bucketKeys, metricMap, rows]);

  return (
    <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" overflowX="auto">
      <Table size="sm" variant="unstyled">
        <Thead>
          <Tr>
            <Th rowSpan={2} textAlign="left" borderBottom="1px solid" borderColor="whiteAlpha.300" width="220px">
              Hand Type
            </Th>
            <Th colSpan={bucketKeys.length} textAlign="center" borderBottom="1px solid" borderColor="whiteAlpha.300">
              Turn Bet Size
            </Th>
          </Tr>
          <Tr>
            {bucketOrder.map((bucket) => (
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
              const value = metricMap.get(key)?.events ?? 0;
              const { bg, color } = deriveCountColor(value, maxEvents);
              return (
                <Td key={`hand-events-${key}`} isNumeric fontWeight="semibold" bg={bg} color={color}>
                  {value.toLocaleString()}
                </Td>
              );
            })}
          </Tr>
          {rows.map((rowKey) => (
            <Tr key={rowKey}>
              <Th scope="row">{rowKey}</Th>
              {bucketKeys.map((key) => {
                const metric = metricMap.get(key);
                const events = metric?.events ?? 0;
                const count = metric?.categories?.[rowKey] ?? 0;
                const percent = events > 0 ? (count / events) * 100 : 0;
                const { bg, color } = derivePercentColor(percent, columnMax[key] ?? 0);
                return (
                  <Td key={`${rowKey}-${key}`} isNumeric bg={bg} color={color}>
                    {percent.toFixed(1)}%
                  </Td>
                );
              })}
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
};

export default LineExplorer;
