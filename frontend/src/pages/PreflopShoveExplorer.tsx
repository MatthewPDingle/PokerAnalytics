import { Box, Flex, Heading, SimpleGrid, Spinner, Stack, Text } from '@chakra-ui/react';
import RangeGrid from '../components/RangeGrid';
import ValueGrid from '../components/ValueGrid';
import { usePreflopShoveData } from '../hooks/usePreflopShoveData';

const EV_DISABLED_IDS = new Set(['three_bet_shove', 'four_bet_shove', 'five_plus_bet_shove']);
const EQUITY_SECTION_ORDER = [
  'first_to_bet_leq30',
  'first_to_bet_gt30',
  'three_bet_shove',
  'four_bet_shove',
  'five_plus_bet_shove',
];

const SummaryList = ({
  title,
  items,
}: {
  title: string;
  items: { group: string; percent: number }[];
}) => (
  <Box bg="blackAlpha.500" borderRadius="md" p={4} borderWidth="1px" borderColor="whiteAlpha.200">
    <Heading as="h4" size="sm" mb={3} color="brand.200">
      {title}
    </Heading>
    <Stack spacing={1} fontSize="sm">
      {items.map((item) => (
        <Box key={item.group} display="flex" justifyContent="space-between">
          <Text>{item.group}</Text>
          <Text fontWeight="semibold">{item.percent.toFixed(1)}%</Text>
        </Box>
      ))}
    </Stack>
  </Box>
);

const PreflopShoveExplorer = () => {
  const { loading, error, ranges, equity } = usePreflopShoveData();

  const equityById = new Map(equity.map((item) => [item.id, item]));
  const orderedRanges = [...ranges].sort((a, b) => {
    const aIndex = EQUITY_SECTION_ORDER.indexOf(a.id);
    const bIndex = EQUITY_SECTION_ORDER.indexOf(b.id);
    return (aIndex === -1 ? Number.MAX_SAFE_INTEGER : aIndex) -
      (bIndex === -1 ? Number.MAX_SAFE_INTEGER : bIndex);
  });

  if (loading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" minH="60vh">
        <Spinner size="xl" />
      </Box>
    );
  }

  if (error) {
    return (
      <Box bg="red.600" color="white" p={6} borderRadius="md">
        <Heading size="md" mb={2}>
          Failed to load
        </Heading>
        <Text>{error}</Text>
      </Box>
    );
  }

  return (
    <Stack spacing={10} py={{ base: 6, md: 10 }} px={{ base: 4, md: 8 }} maxW="1500px" mx="auto">
      <Stack spacing={3}>
        <Heading size="2xl">Preflop Shove Explorer</Heading>
        <Text color="whiteAlpha.800" maxW="4xl">
          Review shove ranges and calling outcomes across common preflop scenarios. Each heatmap displays the 13×13
          starting-hand matrix with pocket pairs on the diagonal, suited combinations above, and offsuit combinations
          below. Calling equity and EV tables reflect the performance of a caller facing the corresponding shove.
        </Text>
      </Stack>

      <Stack spacing={8}>
        {orderedRanges.map((range) => {
          const equityItem = equityById.get(range.id);
          const showEv = Boolean(
            equityItem &&
              !EV_DISABLED_IDS.has(equityItem.id) &&
              equityItem.ev_grid.values &&
              equityItem.ev_grid.values.length > 0
          );

          return (
            <Box key={range.id} borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" p={6} bg="blackAlpha.400">
              <Stack spacing={4}>
                <Flex align="baseline" justify="space-between" gap={4} wrap="wrap">
                  <Heading size="lg">{range.label}</Heading>
                  <Text fontSize="sm" color="whiteAlpha.700">
                    {range.events.toLocaleString()} events
                  </Text>
                </Flex>
                <Flex
                  direction={{ base: 'column', xl: 'row' }}
                  gap={4}
                  align="flex-start"
                  flexWrap={{ base: 'wrap', xl: 'nowrap' }}
                >
                  <Box overflowX="auto">
                    <Stack spacing={2} align="flex-start">
                      <Heading as="h4" size="sm" color="brand.200" px={1}>
                        Shoving Range (%)
                      </Heading>
                      <RangeGrid
                        variant="frequency"
                        rows={range.grid.rows}
                        cols={range.grid.cols}
                        values={range.grid.values}
                      />
                    </Stack>
                  </Box>
                  {equityItem && (
                    <Box overflowX="auto">
                      <Stack spacing={2} align="flex-start">
                        <Heading as="h4" size="sm" color="brand.200" px={1}>
                          Calling Equity (%)
                        </Heading>
                        <RangeGrid
                          rows={equityItem.equity_grid.rows}
                          cols={equityItem.equity_grid.cols}
                          values={equityItem.equity_grid.values}
                        />
                      </Stack>
                    </Box>
                  )}
                  {showEv && equityItem && (
                    <Box overflowX="auto">
                      <Stack spacing={2} align="flex-start">
                        <Heading as="h4" size="sm" color="brand.200" px={1}>
                          Calling EV (bb)
                        </Heading>
                        <ValueGrid rows={equityItem.ev_grid.rows} cols={equityItem.ev_grid.cols} values={equityItem.ev_grid.values} />
                      </Stack>
                    </Box>
                  )}
                </Flex>
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4} maxW="440px">
                  <SummaryList title="Hand Groups" items={range.summary_primary} />
                  <SummaryList title="Aggregate Buckets" items={range.summary_secondary} />
                </SimpleGrid>
              </Stack>
            </Box>
          );
        })}
      </Stack>
    </Stack>
  );
};

export default PreflopShoveExplorer;
