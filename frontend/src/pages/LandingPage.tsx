import { Box, Heading, Stack, Text, VStack } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

const PAGES = [
  {
    title: 'Preflop Shove Explorer',
    description: 'Population shove frequencies, hand-group summaries, and simulated equity/EV heatmaps.',
    to: '/preflop-shove-explorer',
  },
  {
    title: 'Preflop Response Curves',
    description: 'Fold/call/3-bet tendencies and chip EV across preflop sizing choices for specific spots.',
    to: '/preflop/response-curves',
  },
  {
    title: 'Performance Overview',
    description: 'Aggregate hero results and position splits across every table configuration.',
    to: '/performance/overview',
  },
  {
    title: 'Performance by Opponent Count',
    description: 'Hero win rate, VPIP/PFR, and 3-bet tendencies grouped by table size with position-level splits.',
    to: '/performance/opponent-count',
  },
];

const LandingPage = () => (
  <Box as="main" px={{ base: 4, md: 8 }} py={{ base: 8, md: 14 }} maxW="800px" mx="auto">
    <VStack spacing={8} align="stretch">
      <Stack spacing={3}>
        <Heading size="2xl">Poker Analytics</Heading>
        <Text color="whiteAlpha.800">
          Jump straight into the modules below. New dashboards will appear here as we port the legacy notebooks
          and build fresh analyses.
        </Text>
      </Stack>

      <Stack spacing={6}>
        {PAGES.sort((a, b) => a.title.localeCompare(b.title)).map((page) => (
          <Box
            as={RouterLink}
            key={page.to}
            to={page.to}
            borderWidth="1px"
            borderColor="whiteAlpha.200"
            borderRadius="lg"
            p={6}
            bg="blackAlpha.400"
            _hover={{ borderColor: 'brand.400', textDecoration: 'none' }}
          >
            <Heading size="md" mb={2}>
              {page.title}
            </Heading>
            <Text color="whiteAlpha.800">{page.description}</Text>
          </Box>
        ))}
      </Stack>
    </VStack>
  </Box>
);

export default LandingPage;
