import {
  Badge,
  Box,
  Button,
  ButtonGroup,
  Flex,
  Heading,
  Spinner,
  Stack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  Wrap,
  WrapItem,
} from '@chakra-ui/react';
import { useEffect, useMemo, useState } from 'react';

import { useActionRecommendations } from '../hooks/useActionRecommendations';
import { useActiveDataSource } from '../hooks/useActiveDataSource';

type Street = 'Flop' | 'Turn' | 'River';
type Situation = 'Bluff' | 'Value';

const streetOptions: Street[] = ['Flop', 'Turn', 'River'];
const situationOptions: Situation[] = ['Bluff', 'Value'];

type FilterState = {
  street: Street;
  preflopAction: string | null;
  betClassification: string | null;
  flopTexture: string | null;
  players: string | null;
  bettorPosition: string | null;
  sprBucket: string | null;
  situation: Situation;
};

const ActionQuickReference = () => {
  const { activeSourceKey } = useActiveDataSource();
  const { rows, loading, error } = useActionRecommendations(activeSourceKey);

  const [filters, setFilters] = useState<FilterState>({
    street: 'Flop',
    preflopAction: 'All Preflop Pots',
    betClassification: 'All Bet Types',
    flopTexture: 'All Textures',
    players: 'Any',
    bettorPosition: 'Any',
    sprBucket: 'All SPRs',
    situation: 'Bluff',
  });

  const resetFilters = () => {
    setFilters({
      street: 'Flop',
      preflopAction: 'All Preflop Pots',
      betClassification: 'All Bet Types',
      flopTexture: 'All Textures',
      players: 'Any',
      bettorPosition: 'Any',
      sprBucket: 'All SPRs',
      situation: 'Bluff',
    });
  };

  const optionSets = useMemo(() => {
    const sortWithAllFirst = (values: string[]) => {
      const unique = Array.from(new Set(values));
      unique.sort((a, b) => {
        const aIsAll = a.toLowerCase().startsWith('all ') || a.toLowerCase() === 'any';
        const bIsAll = b.toLowerCase().startsWith('all ') || b.toLowerCase() === 'any';
        if (aIsAll && !bIsAll) return -1;
        if (!aIsAll && bIsAll) return 1;
        return a.localeCompare(b);
      });
      return unique;
    };

    const preflopActionsSet = new Set<string>();
    const betClassificationsSet = new Set<string>();
    const texturesSet = new Set<string>();
    const playersSet = new Set<string>();
    const positionsSet = new Set<string>();
    const sprBucketsSet = new Set<string>();

    const betClassStreetMap = new Map<string, Set<Street>>();
    const textureStreetMap = new Map<string, Set<Street>>();
    const textureStreetHasDataMap = new Map<string, Set<Street>>();

    rows.forEach((row) => {
      preflopActionsSet.add(row.preflopAction);
      betClassificationsSet.add(row.betClassification);
      texturesSet.add(row.flopTexture);
      playersSet.add(row.players);
      positionsSet.add(row.bettorPosition);
      sprBucketsSet.add(row.sprBucket);

      const bcSet = betClassStreetMap.get(row.betClassification) ?? new Set<Street>();
      bcSet.add(row.street);
      betClassStreetMap.set(row.betClassification, bcSet);

      const texSet = textureStreetMap.get(row.flopTexture) ?? new Set<Street>();
      texSet.add(row.street);
      textureStreetMap.set(row.flopTexture, texSet);

      const hasSufficientData =
        row.sampleSize >= 50 && (row.situation !== 'Bluff' || (row.foldSurplus ?? 0) >= 5);
      if (hasSufficientData) {
        const dataSet = textureStreetHasDataMap.get(row.flopTexture) ?? new Set<Street>();
        dataSet.add(row.street);
        textureStreetHasDataMap.set(row.flopTexture, dataSet);
      }
    });

    const texturesOrdered = Array.from(texturesSet);
    texturesOrdered.sort((a, b) => {
      if (a === b) return 0;
      const lowerA = a.toLowerCase();
      const lowerB = b.toLowerCase();
      const isAllA = lowerA.startsWith('all ');
      const isAllB = lowerB.startsWith('all ');
      if (isAllA && !isAllB) return -1;
      if (!isAllA && isAllB) return 1;

      const groupFor = (label: string): number => {
        const streets = textureStreetMap.get(label);
        if (streets?.has('Flop')) return 0;
        if (streets?.has('Turn')) return 1;
        if (streets?.has('River')) return 2;
        return 3;
      };

      const gA = groupFor(a);
      const gB = groupFor(b);
      if (gA !== gB) return gA - gB;
      return a.localeCompare(b);
    });

    const betClassificationsOrdered = Array.from(betClassificationsSet).filter((value) => {
      const lower = value.toLowerCase();
      return lower !== 'all bet types';
    });
    betClassificationsOrdered.sort((a, b) => {
      if (a === b) return 0;

      const lowerA = a.toLowerCase();
      const lowerB = b.toLowerCase();
      const aIsAll = lowerA.startsWith('all ') || lowerA === 'any';
      const bIsAll = lowerB.startsWith('all ') || lowerB === 'any';
      if (aIsAll && !bIsAll) return -1;
      if (!aIsAll && bIsAll) return 1;

      const streetGroup = (label: string): number => {
        const streets = betClassStreetMap.get(label);
        if (streets?.has('Flop')) return 0;
        if (streets?.has('Turn')) return 1;
        if (streets?.has('River')) return 2;
        return 3;
      };

      const gA = streetGroup(a);
      const gB = streetGroup(b);
      if (gA !== gB) return gA - gB;

      return a.localeCompare(b);
    });

    return {
      preflopActions: sortWithAllFirst(Array.from(preflopActionsSet)),
      betClassifications: betClassificationsOrdered,
      textures: texturesOrdered,
      players: sortWithAllFirst(Array.from(playersSet)),
      positions: sortWithAllFirst(Array.from(positionsSet)),
      sprBuckets: sortWithAllFirst(Array.from(sprBucketsSet)),
      betClassStreetMap,
      textureStreetMap,
      textureStreetHasDataMap,
    };
  }, [rows]);

  const filteredRows = useMemo(() => {
    const streetRows = rows.filter((row) => row.street === filters.street);

    const matches = streetRows.filter((row) => {
      if (filters.situation && row.situation !== filters.situation) {
        return false;
      }
      if (filters.preflopAction && row.preflopAction !== filters.preflopAction) {
        return false;
      }
      if (filters.betClassification && row.betClassification !== filters.betClassification) {
        return false;
      }
      if (filters.flopTexture && row.flopTexture !== filters.flopTexture) {
        return false;
      }
      if (filters.players && row.players !== filters.players) {
        return false;
      }
      if (filters.bettorPosition && row.bettorPosition !== filters.bettorPosition) {
        return false;
      }
      if (filters.sprBucket && row.sprBucket !== filters.sprBucket) {
        return false;
      }
      return true;
    });

    const withThresholds = matches.filter((row) => {
      if (!row.sampleSize || row.sampleSize < 50) {
        return false;
      }
      if (row.situation === 'Bluff') {
        if (row.foldSurplus === null || row.foldSurplus < 5) {
          return false;
        }
      }
      return true;
    });

    return withThresholds.sort((a, b) => {
      if (a.situation === 'Bluff' && b.situation === 'Bluff') {
        const aSurplus = a.foldSurplus ?? 0;
        const bSurplus = b.foldSurplus ?? 0;
        if (bSurplus !== aSurplus) {
          return bSurplus - aSurplus;
        }
        return b.sampleSize - a.sampleSize;
      }
      if (a.situation === 'Value' && b.situation === 'Value') {
        const aPot = a.potShareAdded ?? 0;
        const bPot = b.potShareAdded ?? 0;
        if (bPot !== aPot) {
          return bPot - aPot;
        }
        return b.sampleSize - a.sampleSize;
      }
      return a.rank - b.rank;
    });
  }, [rows, filters]);

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
          Failed to load recommendations
        </Heading>
        <Text>{error}</Text>
      </Box>
    );
  }

  const {
    preflopActions,
    betClassifications,
    textures,
    players,
    positions,
    sprBuckets,
    betClassStreetMap,
    textureStreetMap,
    textureStreetHasDataMap,
  } = optionSets;

  const sprBucketsOrdered = [...sprBuckets].sort((a, b) => {
    if (a === b) return 0;
    const order: Record<string, number> = {
      'All SPRs': 0,
      '<= 1': 1,
      '1-2': 2,
      '2-4': 3,
      '4-6': 4,
      '6-10': 5,
      '10+': 6,
    };
    const aIndex = order[a] ?? 999;
    const bIndex = order[b] ?? 999;
    if (aIndex !== bIndex) {
      return aIndex - bIndex;
    }
    return a.localeCompare(b);
  });

  const preflopActionsOrdered = [...preflopActions].sort((a, b) => {
    if (a === b) return 0;
    const order: Record<string, number> = {
      'All Preflop Pots': 0,
      'Single-Raise Pot': 1,
      '3-Bet+ Pot': 2,
      'Limped Pot (No Raise)': 3,
    };
    const aIndex = order[a] ?? 999;
    const bIndex = order[b] ?? 999;
    if (aIndex !== bIndex) {
      return aIndex - bIndex;
    }
    return a.localeCompare(b);
  });

  const texturesForStreet = textures;

  const formatPercent = (value: number | null) => {
    if (value == null) return '–';
    return `${value.toFixed(1)}%`;
  };

  const formatFoldSurplus = (value: number | null) => {
    if (value == null) return '–';
    return `${value.toFixed(1)}%`;
  };

  const formatPotShare = (value: number | null) => {
    if (value == null) return '–';
    return `${value.toFixed(2)}×`;
  };

  return (
    <Stack spacing={8} py={{ base: 6, md: 10 }} px={{ base: 4, md: 8 }} maxW="1500px" mx="auto">
      <Stack spacing={4}>
        <Stack
          direction={{ base: 'column', md: 'row' }}
          justify="space-between"
          align={{ base: 'flex-start', md: 'center' }}
          gap={4}
        >
          <Stack spacing={3}>
            <Heading size="2xl">Action Quick Reference</Heading>
            <Text color="whiteAlpha.800" maxW="4xl">
              Filter by street, preflop action, texture, and stack depth to see recommended bluff and value bet sizes
              derived from the response matrices. Bluff recommendations require at least 50 hands and a minimum 5
              percentage point fold surplus; value recommendations are ordered by average pot share added.
            </Text>
          </Stack>
          <Button size="sm" variant="outline" onClick={resetFilters}>
            Reset Filters
          </Button>
        </Stack>
      </Stack>

      <Stack spacing={4}>
        <Flex gap={8} wrap="wrap" direction={{ base: 'column', lg: 'row' }}>
          <Stack flex="1" minW={0} spacing={4}>
            <Stack spacing={2}>
              <Text fontSize="sm" color="whiteAlpha.700">
                Street
              </Text>
              <ButtonGroup size="sm" isAttached variant="outline">
                {streetOptions.map((street) => (
                  <Button
                    key={street}
                    onClick={() =>
                      setFilters((prev) => ({
                        ...prev,
                        street,
                        // Keep current filters but ensure we stay on the "all" texture bucket
                        flopTexture: 'All Textures',
                      }))
                    }
                    colorScheme={filters.street === street ? 'brand' : undefined}
                    variant={filters.street === street ? 'solid' : 'outline'}
                  >
                    {street}
                  </Button>
                ))}
              </ButtonGroup>
            </Stack>

            <Stack spacing={2}>
              <Text fontSize="sm" color="whiteAlpha.700">
                Bet Classification
              </Text>
              <Wrap>
                <WrapItem>
                  <Button
                    size="sm"
                    variant={filters.betClassification === 'All Bet Types' ? 'solid' : 'outline'}
                    colorScheme={filters.betClassification === 'All Bet Types' ? 'brand' : undefined}
                    onClick={() =>
                      setFilters((prev) => ({
                        ...prev,
                        betClassification: 'All Bet Types',
                      }))
                    }
                  >
                    Any
                  </Button>
                </WrapItem>
                {betClassifications.map((value) => (
                  <WrapItem key={value}>
                    <Button
                      size="sm"
                      variant={filters.betClassification === value ? 'solid' : 'outline'}
                      colorScheme={filters.betClassification === value ? 'brand' : undefined}
                      isDisabled={
                        !betClassStreetMap.get(value)?.has(filters.street) &&
                        filters.betClassification !== value
                      }
                      onClick={() =>
                        setFilters((prev) => ({
                          ...prev,
                          betClassification:
                            prev.betClassification === value ? 'All Bet Types' : value,
                        }))
                      }
                    >
                      {value}
                    </Button>
                  </WrapItem>
                ))}
              </Wrap>
            </Stack>

            <Stack spacing={2}>
              <Text fontSize="sm" color="whiteAlpha.700">
                Players
              </Text>
              <Wrap>
                {players.map((value) => (
                  <WrapItem key={value}>
                    <Button
                      size="sm"
                      variant={filters.players === value ? 'solid' : 'outline'}
                      colorScheme={filters.players === value ? 'brand' : undefined}
                      onClick={() =>
                        setFilters((prev) => ({
                          ...prev,
                          players: prev.players === value ? null : value,
                        }))
                      }
                    >
                      {value === 'Any' ? 'Any' : `${value} Players`}
                    </Button>
                  </WrapItem>
                ))}
              </Wrap>
            </Stack>

            <Stack spacing={2}>
              <Text fontSize="sm" color="whiteAlpha.700">
                SPR Bucket
              </Text>
              <Wrap>
                {sprBucketsOrdered.map((value) => (
                  <WrapItem key={value}>
                    <Button
                      size="sm"
                      variant={filters.sprBucket === value ? 'solid' : 'outline'}
                      colorScheme={filters.sprBucket === value ? 'brand' : undefined}
                      onClick={() =>
                        setFilters((prev) => ({
                          ...prev,
                          sprBucket: prev.sprBucket === value ? null : value,
                        }))
                      }
                    >
                      {value}
                    </Button>
                  </WrapItem>
                ))}
              </Wrap>
            </Stack>
          </Stack>

          <Stack flex="1" minW={0} spacing={4}>
            <Stack spacing={2}>
              <Text fontSize="sm" color="whiteAlpha.700">
                Preflop Action
              </Text>
              <Wrap>
                {preflopActionsOrdered.map((value) => (
                  <WrapItem key={value}>
                    <Button
                      size="sm"
                      variant={filters.preflopAction === value ? 'solid' : 'outline'}
                      colorScheme={filters.preflopAction === value ? 'brand' : undefined}
                      onClick={() =>
                        setFilters((prev) => ({
                          ...prev,
                          preflopAction: prev.preflopAction === value ? null : value,
                        }))
                      }
                    >
                      {value}
                    </Button>
                  </WrapItem>
                ))}
              </Wrap>
            </Stack>

            <Stack spacing={2}>
              <Text fontSize="sm" color="whiteAlpha.700">
                Board Texture
              </Text>
              <Wrap>
                {texturesForStreet.map((value) => {
                  const isAllTextures = value === 'All Textures';
                  const hasStreetData = textureStreetMap.get(value)?.has(filters.street) ?? false;
                  const isPrimaryForStreet = isAllTextures || hasStreetData;
                  const isSelected = filters.flopTexture === value;

                  return (
                    <WrapItem key={value}>
                      <Button
                        size="sm"
                        variant={isSelected ? 'solid' : 'outline'}
                        colorScheme={isSelected ? 'brand' : undefined}
                        opacity={isPrimaryForStreet ? 1 : 0.4}
                        onClick={() =>
                          setFilters((prev) => ({
                            ...prev,
                            flopTexture: prev.flopTexture === value ? null : value,
                          }))
                        }
                      >
                        {value}
                      </Button>
                    </WrapItem>
                  );
                })}
              </Wrap>
            </Stack>

            <Stack spacing={2}>
              <Text fontSize="sm" color="whiteAlpha.700">
                Bettor Position
              </Text>
              <Wrap>
                {positions.map((value) => (
                  <WrapItem key={value}>
                    <Button
                      size="sm"
                      variant={filters.bettorPosition === value ? 'solid' : 'outline'}
                      colorScheme={filters.bettorPosition === value ? 'brand' : undefined}
                      onClick={() =>
                        setFilters((prev) => ({
                          ...prev,
                          bettorPosition: prev.bettorPosition === value ? null : value,
                        }))
                      }
                    >
                      {value}
                    </Button>
                  </WrapItem>
                ))}
              </Wrap>
            </Stack>

            <Stack spacing={2}>
              <Text fontSize="sm" color="whiteAlpha.700">
                Situation
              </Text>
              <ButtonGroup size="sm" variant="outline">
                {situationOptions.map((value) => (
                  <Button
                    key={value}
                    variant={filters.situation === value ? 'solid' : 'outline'}
                    colorScheme={filters.situation === value ? 'brand' : undefined}
                    onClick={() =>
                      setFilters((prev) => ({
                        ...prev,
                        situation: value,
                      }))
                    }
                  >
                    {value}
                  </Button>
                ))}
              </ButtonGroup>
            </Stack>
          </Stack>
        </Flex>
      </Stack>

      <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" bg="blackAlpha.400" p={4}>
        <Flex justify="space-between" align="center" mb={3}>
          <Heading size="md">Recommended Actions</Heading>
          <Text fontSize="sm" color="whiteAlpha.700">
            {filteredRows.length === 1 ? '1 match' : `${filteredRows.length} matches`}
          </Text>
        </Flex>
        <Box overflowX="auto">
          <Table size="sm" variant="simple">
            <Thead>
              <Tr>
                <Th>Action</Th>
                <Th isNumeric>Fold Surplus</Th>
                <Th isNumeric># Events</Th>
                <Th isNumeric>Fold %</Th>
                <Th isNumeric>Call %</Th>
                <Th isNumeric>Raise %</Th>
                <Th isNumeric>Avg Bet Size</Th>
                <Th isNumeric>Breakeven Fold %</Th>
                <Th isNumeric>Avg Pot Share Added</Th>
              </Tr>
            </Thead>
            <Tbody>
              {filteredRows.map((row, index) => (
                <Tr key={`${row.street}-${index}`}>
                  <Td>
                    <Text fontSize="lg" fontWeight="semibold" color="brand.200">
                      {row.bucketLabel ? `Bet ${row.bucketLabel}` : row.action.split(' — ')[0]}
                    </Text>
                  </Td>
                  <Td isNumeric>{formatFoldSurplus(row.foldSurplus)}</Td>
                  <Td isNumeric>{row.sampleSize.toLocaleString()}</Td>
                  <Td isNumeric>{formatPercent(row.foldPct)}</Td>
                  <Td isNumeric>{formatPercent(row.callPct)}</Td>
                  <Td isNumeric>{formatPercent(row.raisePct)}</Td>
                  <Td isNumeric>
                    {row.avgBetPct != null ? `${row.avgBetPct.toFixed(1)}%` : row.bucketLabel || '–'}
                  </Td>
                  <Td isNumeric>{formatPercent(row.breakevenFoldPct)}</Td>
                  <Td isNumeric>{formatPotShare(row.potShareAdded)}</Td>
                </Tr>
              ))}
              {filteredRows.length === 0 && (
                <Tr>
                  <Td colSpan={9}>
                    <Text color="whiteAlpha.700" fontStyle="italic">
                      No recommendations match the current filters.
                    </Text>
                  </Td>
                </Tr>
              )}
            </Tbody>
          </Table>
        </Box>
      </Box>
    </Stack>
  );
};

export default ActionQuickReference;
