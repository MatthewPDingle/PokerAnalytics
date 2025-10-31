import { InfoOutlineIcon } from '@chakra-ui/icons';
import { Badge, Box, HStack, Stack, Text, Tooltip, Wrap, WrapItem } from '@chakra-ui/react';
import { memo } from 'react';

import { FLOP_TEXTURE_DEFINITIONS, TURN_RIVER_TEXTURE_DEFINITIONS } from './boardTextureDefinitions';

export type DerivedFilterCategory = {
  key: string;
  title: string;
  filters: Array<{ id: string; label: string; detail?: string }>;
};

type DerivedFiltersPanelProps = {
  highlightFilters: {
    selectionLabel: string;
    categories: DerivedFilterCategory[];
    boardCategories: DerivedFilterCategory[];
  } | null;
  disabledFilters: Set<string>;
  toggleFilter: (id: string) => void;
};

export const DerivedFiltersPanel = memo(({ highlightFilters, disabledFilters, toggleFilter }: DerivedFiltersPanelProps) => {
  return (
    <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" p={4}>
      <Stack spacing={3}>
        <Text fontWeight="semibold">Derived Filters</Text>
        {highlightFilters ? (
          <Stack spacing={3}>
            <Text fontSize="sm" color="black">
              {highlightFilters.selectionLabel}
            </Text>
            {highlightFilters.categories.map((category) => (
              <FilterCategory
                key={category.key}
                category={category}
                disabledFilters={disabledFilters}
                toggleFilter={toggleFilter}
                colorScheme="purple"
              />
            ))}
            <BoardCategorySection
              categories={highlightFilters.boardCategories}
              disabledFilters={disabledFilters}
              toggleFilter={toggleFilter}
            />
          </Stack>
        ) : (
          <Text fontSize="sm" color="whiteAlpha.600">
            Select a player action to preview filter constraints derived from the action matrix.
          </Text>
        )}
      </Stack>
    </Box>
  );
});

DerivedFiltersPanel.displayName = 'DerivedFiltersPanel';

type FilterCategoryProps = {
  category: DerivedFilterCategory;
  disabledFilters: Set<string>;
  toggleFilter: (id: string) => void;
  colorScheme: string;
};

const FilterCategory = ({ category, disabledFilters, toggleFilter, colorScheme }: FilterCategoryProps) => (
  <Box>
    <Text fontWeight="semibold" fontSize="sm">
      {category.title}
    </Text>
    {category.filters.length ? (
      <Wrap mt={2} spacing={2}>
        {category.filters.map((filter) => {
          const disabled = disabledFilters.has(filter.id);
          return (
            <WrapItem key={filter.id}>
              <Badge
                as="button"
                px={2}
                py={1}
                borderRadius="md"
                colorScheme={disabled ? 'gray' : colorScheme}
                variant={disabled ? 'outline' : 'solid'}
                opacity={disabled ? 0.6 : 1}
                onClick={() => toggleFilter(filter.id)}
              >
                <Stack spacing={0} align="flex-start">
                  <Text>{filter.label}</Text>
                  {filter.detail && (
                    <Text fontSize="xs" opacity={disabled ? 0.6 : 0.8}>
                      {filter.detail}
                    </Text>
                  )}
                </Stack>
              </Badge>
            </WrapItem>
          );
        })}
      </Wrap>
    ) : (
      <Text fontSize="sm" color="whiteAlpha.500" mt={1}>
        No filters yet.
      </Text>
    )}
  </Box>
);

type BoardCategorySectionProps = {
  categories: DerivedFilterCategory[];
  disabledFilters: Set<string>;
  toggleFilter: (id: string) => void;
};

const BoardCategorySection = ({ categories, disabledFilters, toggleFilter }: BoardCategorySectionProps) => (
  <Stack spacing={2}>
    <HStack spacing={2} align="center">
      <Text fontWeight="semibold" fontSize="sm">
        Board Textures
      </Text>
      <Tooltip
        label={
          <Stack spacing={2} align="flex-start" w="max-content">
            <Box>
              <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" color="black">
                Flop
              </Text>
              {Object.entries(FLOP_TEXTURE_DEFINITIONS).map(([key, description]) => (
                <Text key={key} fontSize="xs">
                  {key} - {description}
                </Text>
              ))}
            </Box>
            <Box>
              <Text fontSize="xs" fontWeight="semibold" textTransform="uppercase" color="black">
                Turn / River
              </Text>
              {Object.entries(TURN_RIVER_TEXTURE_DEFINITIONS).map(([key, description]) => (
                <Text key={key} fontSize="xs">
                  {key} - {description}
                </Text>
              ))}
            </Box>
          </Stack>
        }
        placement="top"
        openDelay={200}
        maxW="440px"
      >
        <Box as="span" color="whiteAlpha.600" cursor="help">
          <InfoOutlineIcon boxSize={3} />
        </Box>
      </Tooltip>
    </HStack>
    {categories.map((category) => (
      <FilterCategory
        key={category.key}
        category={category}
        disabledFilters={disabledFilters}
        toggleFilter={toggleFilter}
        colorScheme="cyan"
      />
    ))}
  </Stack>
);

BoardCategorySection.displayName = 'BoardCategorySection';
