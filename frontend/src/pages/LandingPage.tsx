import { Box, Heading, Stack, Text, VStack } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

const CORE_PAGES = [
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
  {
    title: 'Preflop Shove Explorer',
    description: 'Population shove frequencies, hand-group summaries, and simulated equity/EV heatmaps.',
    to: '/preflop-shove-explorer',
  },
  {
    title: 'Action Quick Reference',
    description: 'Shortcut recommendations for bluff and value bet sizes across flop, turn, and river based on response matrices.',
    to: '/actions/quick-reference',
  },
  {
    title: 'Flop Response Matrix',
    description: 'Villain fold/call/raise rates by flop bet size with classification and position filters.',
    to: '/flop/response-matrix',
  },
  {
    title: 'Turn Response Matrix',
    description: 'Villain fold/call/raise rates by turn bet size with line and position filters.',
    to: '/turn/response-matrix',
  },
  {
    title: 'River Response Matrix',
    description: 'Villain fold/call/raise rates by river bet size with advanced line, texture, and position filters.',
    to: '/river/response-matrix',
  },
];

const EXPERIMENTAL_PAGES = [
  {
    title: 'Preflop Response Curves',
    description: 'Fold/call/3-bet tendencies and chip EV across preflop sizing choices for specific spots.',
    to: '/preflop/response-curves',
  },
  {
    title: 'Line Explorer',
    description: 'Analyze multi-street betting lines such as flop check-call into turn bets with responder breakdowns.',
    to: '/lines/explorer',
  },
];

const LandingPage = () => (
  <Box as="main" px={{ base: 4, md: 8 }} py={{ base: 8, md: 14 }} maxW="800px" mx="auto">
    <VStack spacing={8} align="stretch">
      <Stack spacing={6}>
        <Stack spacing={3}>
          <Heading size="lg">Dashboards</Heading>
          <Stack spacing={6}>
            {CORE_PAGES.map((page) => (
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
        </Stack>

        <Stack spacing={3}>
          <Heading size="lg">Experimental</Heading>
          <Stack spacing={6}>
            {EXPERIMENTAL_PAGES.map((page) => (
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
        </Stack>
      </Stack>
    </VStack>
  </Box>
);

export default LandingPage;
