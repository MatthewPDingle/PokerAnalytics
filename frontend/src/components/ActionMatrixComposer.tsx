import {
  Badge,
  Box,
  Button,
  ButtonGroup,
  Flex,
  IconButton,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Radio,
  RadioGroup,
  Slider,
  SliderFilledTrack,
  SliderThumb,
  SliderTrack,
  HStack,
  SimpleGrid,
  Stack,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  Tooltip,
  useDisclosure,
  useToast,
} from '@chakra-ui/react';
import { RepeatIcon, SettingsIcon } from '@chakra-ui/icons';
import { Dispatch, useCallback, useEffect, useMemo, useState } from 'react';

import {
  PRE_FLOP_SEQUENCE_ORDER,
  POST_FLOP_SEQUENCE_ORDER,
  SeatAction,
  SeatPosition,
  SeatState,
  Street,
  StreetActionStep,
  TableComposerAction,
  TableComposerState,
  STREET_ORDER,
} from '../state/tableComposer';

export type BucketOption = { key: string; label: string };

type ActionMatrixComposerProps = {
  state: TableComposerState;
  dispatch: Dispatch<TableComposerAction>;
  bucketOptions: BucketOption[];
};

type ActionChoice = 'check' | 'call' | 'bet' | 'raise' | 'fold' | 'limp';

type ActionOption = {
  value: ActionChoice;
  label: string;
};

type EditorState = {
  step: StreetActionStep;
  seat: SeatState;
  street: Street;
  sequence: StreetActionStep[];
  stepIndex: number;
  options: ActionOption[];
  treatRaiseAsOpen: boolean;
  potBefore: number;
  toCall: number;
  contribution: number;
  currentAction: SeatAction | undefined;
  minRaiseTo: number;
  stackBefore: number;
  maxContribution: number;
  currentBet: number;
  startingStack: number;
};

type ActionSnapshot = {
  potBefore: number;
  toCall: number;
  contribution: number;
  minRaiseTo: number;
  stackBefore: number;
  stackAfter: number;
  maxContribution: number;
  currentBet: number;
  startingStack: number;
  resultContribution: number;
  resultAdded: number;
};

type PotTimeline = {
  actionContext: Map<string, ActionSnapshot>;
  totalPot: number;
  streetStartPot: Record<Street, number>;
  blindsTotal: number;
};

const DEFAULT_STACK_SIZE = 100;
type BoardStreet = 'flop' | 'turn' | 'river';
const BOARD_CARD_RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
const BOARD_CARD_SUITS = ['s', 'h', 'd', 'c'] as const;
const SUIT_SYMBOLS: Record<string, string> = { s: '♠', h: '♥', d: '♦', c: '♣' };
const SUIT_COLORS: Record<
  string,
  {
    defaultText: string;
    selectedText: string;
    selectedBg: string;
    buttonBg: string;
    buttonBorder: string;
    disabled: string;
  }
> = {
  s: {
    defaultText: 'whiteAlpha.900',
    selectedText: '#1A202C',
    selectedBg: 'whiteAlpha.900',
    buttonBg: 'blackAlpha.800',
    buttonBorder: 'whiteAlpha.700',
    disabled: 'whiteAlpha.300',
  },
  h: {
    defaultText: '#E53E3E',
    selectedText: '#E53E3E',
    selectedBg: 'whiteAlpha.900',
    buttonBg: 'blackAlpha.700',
    buttonBorder: 'red.400',
    disabled: 'whiteAlpha.300',
  },
  d: {
    defaultText: '#4299E1',
    selectedText: '#3182CE',
    selectedBg: 'whiteAlpha.900',
    buttonBg: 'blackAlpha.700',
    buttonBorder: 'blue.400',
    disabled: 'whiteAlpha.300',
  },
  c: {
    defaultText: '#48BB78',
    selectedText: '#38A169',
    selectedBg: 'whiteAlpha.900',
    buttonBg: 'blackAlpha.700',
    buttonBorder: 'green.400',
    disabled: 'whiteAlpha.300',
  },
};
const BOARD_STREETS: BoardStreet[] = ['flop', 'turn', 'river'];
const BOARD_CARD_ROW_HEIGHT = 32;
const BOARD_CARD_WIDTH = 30;

type BoardEditorState = {
  street: BoardStreet;
  required: number;
  selected: Set<string>;
  disabled: Set<string>;
};

const BUCKET_REPRESENTATIVE_RATIO: Record<string, number> = {
  pct_0_25: 0.125,
  pct_25_40: 0.325,
  pct_40_60: 0.5,
  pct_60_80: 0.7,
  pct_80_100: 0.9,
  pct_100_125: 1.125,
  pct_125_200: 1.6,
  pct_200_300: 2.5,
  pct_300_plus: 3.5,
  pct_125_plus: 1.5,
  all_in: 3.5,
  one_bb: 1.0,
};

const BIG_BLIND_SYMBOL = 'BB';
const ROW_HEIGHT = '56px';

const formatPotPercentage = (ratio: number | null): string => {
  if (ratio === null || !Number.isFinite(ratio)) {
    return 'n/a';
  }
  return `${(ratio * 100).toFixed(0)}% pot`;
};

const streetHeader = (street: Street) => street.toUpperCase();

const formatBB = (value: number): string => {
  if (!Number.isFinite(value) || Math.abs(value) < 1e-6) {
    return '0';
  }
  return value.toFixed(2).replace(/\.00$/, '');
};

const isAggressiveAction = (action: SeatAction | undefined) => {
  if (!action) {
    return false;
  }
  return action.action === 'open' || action.action === 'bet' || action.action === 'raise';
};

const computeStreetCompletion = (state: TableComposerState): Record<Street, boolean> => {
  const result = {} as Record<Street, boolean>;
  STREET_ORDER.forEach((street) => {
    const sequence = state.streetSequences[street] ?? [];
    result[street] = sequence.length === 0 || sequence.every((step) => Boolean(state.stepActions[step.id]));
  });
  return result;
};

const isStreetEditable = (completion: Record<Street, boolean>, street: Street) => {
  const index = STREET_ORDER.indexOf(street);
  if (index <= 0) {
    return true;
  }
  for (let i = 0; i < index; i += 1) {
    if (!completion[STREET_ORDER[i]]) {
      return false;
    }
  }
  return true;
};

const resolveBetTarget = (action: SeatAction, potBefore: number, currentBet: number, contribution: number): number => {
  if (action.sizing?.kind === 'bucket') {
    if (action.sizing.key === 'one_bb') {
      return Math.max(currentBet, contribution + 1);
    }
    const ratio = BUCKET_REPRESENTATIVE_RATIO[action.sizing.key] ?? 0.7;
    const target = ratio * potBefore;
    if (target <= 0 && currentBet > 0) {
      return currentBet;
    }
    if (target <= 0) {
      return ratio;
    }
    return Math.max(target, currentBet);
  }
  if (action.sizing?.kind === 'pot_ratio') {
    const target = (action.sizing.value ?? 0) * potBefore;
    return Math.max(target, currentBet);
  }
  if (action.sizing?.kind === 'bb_multiple') {
    const target = (action.sizing.value ?? 0) + contribution;
    return Math.max(target, currentBet);
  }
  return Math.max(currentBet, contribution);
};

const resolveActionContribution = (
  action: SeatAction,
  street: Street,
  potBefore: number,
  contribution: number,
  currentBet: number,
): { added: number; newContribution: number; newBet: number } => {
  switch (action.action) {
    case 'fold':
    case 'check':
      return { added: 0, newContribution: contribution, newBet: currentBet };
    case 'limp':
    case 'call': {
      const target = Math.max(currentBet, contribution);
      const added = Math.max(target - contribution, 0);
      return { added, newContribution: contribution + added, newBet: Math.max(currentBet, contribution + added) };
    }
    case 'open':
    case 'bet':
    case 'raise': {
      const target = resolveBetTarget(action, potBefore, currentBet, contribution);
      const added = Math.max(target - contribution, 0);
      return { added, newContribution: target, newBet: Math.max(currentBet, target) };
    }
    default:
      return { added: 0, newContribution: contribution, newBet: currentBet };
  }
};

const buildPotTimeline = (state: TableComposerState): PotTimeline => {
  const actionContext = new Map<string, ActionSnapshot>();
  const streetStartPot: Record<Street, number> = {
    preflop: 0,
    flop: 0,
    turn: 0,
    river: 0,
  };
  let pot = 0;
  let blindsTotal = 0;

  const contributions: Record<Street, Map<string, number>> = {
    preflop: new Map(),
    flop: new Map(),
    turn: new Map(),
    river: new Map(),
  };
  const seatStartingStacks = new Map<string, number>();
  const totalContributions = new Map<string, number>();

  state.seats.forEach((seat) => {
    if (!seat.isActive) {
      return;
    }
    seatStartingStacks.set(seat.seatId, seat.startingStack ?? DEFAULT_STACK_SIZE);
    totalContributions.set(seat.seatId, 0);
  });

  const smallBlindSeat = state.seats.find((seat) => seat.isActive && seat.position === 'SB');
  if (smallBlindSeat) {
    const sbAmount = 0.5;
    contributions.preflop.set(smallBlindSeat.seatId, sbAmount);
    pot += sbAmount;
    totalContributions.set(
      smallBlindSeat.seatId,
      (totalContributions.get(smallBlindSeat.seatId) ?? 0) + sbAmount,
    );
  }

  const bigBlindSeat = state.seats.find((seat) => seat.isActive && seat.position === 'BB');
  if (bigBlindSeat) {
    const bbAmount = 1;
    contributions.preflop.set(bigBlindSeat.seatId, (contributions.preflop.get(bigBlindSeat.seatId) ?? 0) + bbAmount);
    pot += bbAmount;
    totalContributions.set(
      bigBlindSeat.seatId,
      (totalContributions.get(bigBlindSeat.seatId) ?? 0) + bbAmount,
    );
  }

  blindsTotal = pot;
  streetStartPot.preflop = pot;

  STREET_ORDER.forEach((street) => {
    if (street !== 'preflop') {
      streetStartPot[street] = pot;
    }
    const sequence = state.streetSequences[street] ?? [];
    let currentBet = street === 'preflop' ? 1 : 0;
    let lastRaiseAmount = street === 'preflop' ? 1 : 0;
    const streetContributions = contributions[street];
    sequence.forEach((step) => {
      const contribution = streetContributions.get(step.seatId) ?? 0;
      const toCall = Math.max(currentBet - contribution, 0);
      const startingStack = seatStartingStacks.get(step.seatId) ?? DEFAULT_STACK_SIZE;
      const totalBefore = totalContributions.get(step.seatId) ?? 0;
      const stackBefore = Math.max(startingStack - totalBefore, 0);
      const maxContribution = contribution + stackBefore;
      actionContext.set(step.id, {
        potBefore: pot,
        toCall,
        contribution,
        minRaiseTo: currentBet + Math.max(lastRaiseAmount, 1),
        stackBefore,
        stackAfter: stackBefore,
        maxContribution,
        currentBet,
        startingStack,
        resultContribution: contribution,
        resultAdded: 0,
      });

      const action = state.stepActions[step.id];
      if (!action) {
        return;
      }
      const stackLimit = stackBefore;
      const previousBet = currentBet;
      const result = resolveActionContribution(action, street, pot, contribution, currentBet);
      const appliedAddition = Math.min(result.added, stackLimit);
      const nextContribution = contribution + appliedAddition;
      pot += appliedAddition;
      streetContributions.set(step.seatId, nextContribution);
      const totalAfter = totalBefore + appliedAddition;
      totalContributions.set(step.seatId, totalAfter);
      const actualNewBet = Math.max(currentBet, nextContribution);
      if (actualNewBet > previousBet) {
        lastRaiseAmount = Math.max(actualNewBet - previousBet, 1);
      }
      currentBet = actualNewBet;
      const snapshot = actionContext.get(step.id);
      if (snapshot) {
        snapshot.stackAfter = Math.max(startingStack - totalAfter, 0);
        snapshot.resultContribution = nextContribution;
        snapshot.resultAdded = appliedAddition;
      }
    });
  });

  return {
    actionContext,
    totalPot: pot,
    streetStartPot,
    blindsTotal,
  };
};

const deriveActionOptions = (
  seat: SeatState,
  street: Street,
  sequence: StreetActionStep[],
  stepIndex: number,
  stepActions: Record<string, SeatAction>,
  snapshot: ActionSnapshot | undefined,
): { options: ActionOption[]; treatRaiseAsOpen: boolean } => {
  const priorSteps = sequence.slice(0, stepIndex);
  const priorAggression = priorSteps.some((entry) => isAggressiveAction(stepActions[entry.id]));
  const allPriorResolved = priorSteps.every((entry) => Boolean(stepActions[entry.id]));
  const toCall = snapshot?.toCall ?? 0;
  const isPreflop = street === 'preflop';

  const options: ActionOption[] = [];
  if (isPreflop) {
    options.push({ value: 'fold', label: 'Fold' });
    if (!priorAggression) {
      options.push({ value: 'limp', label: 'Limp' });
      options.push({ value: 'raise', label: 'Raise' });
      if (seat.position === 'BB' && toCall <= 1e-6) {
        options.push({ value: 'check', label: 'Check' });
      }
    } else {
      const callLabel = toCall > 1e-6 ? `Call (${formatBB(toCall)} ${BIG_BLIND_SYMBOL})` : 'Call';
      options.push({ value: 'call', label: callLabel });
      options.push({ value: 'raise', label: 'Raise' });
    }
  } else if (priorAggression || toCall > 1e-6) {
    options.push({ value: 'fold', label: 'Fold' });
    const callLabel = toCall > 1e-6 ? `Call (${formatBB(toCall)} ${BIG_BLIND_SYMBOL})` : 'Call';
    options.push({ value: 'call', label: callLabel });
    options.push({ value: 'raise', label: 'Raise' });
  } else {
    options.push({ value: 'check', label: 'Check' });
    options.push({ value: 'bet', label: 'Bet' });
  }

  const seen = new Set<ActionChoice>();
  const uniqueOptions = options.filter((option) => {
    if (seen.has(option.value)) {
      return false;
    }
    seen.add(option.value);
    return true;
  });

  return {
    options: uniqueOptions,
    treatRaiseAsOpen: isPreflop && !priorAggression,
  };
};

const renderActionBadge = (action?: SeatAction, overrideLabel?: string) => {
  if (!action) {
    return null;
  }
  switch (action.action) {
    case 'call':
      return <Badge colorScheme="blue">CALL</Badge>;
    case 'check':
      return <Badge colorScheme="blue">CHECK</Badge>;
    case 'limp':
      return <Badge colorScheme="blue">LIMP</Badge>;
    case 'fold':
      return <Badge colorScheme="red">FOLD</Badge>;
    case 'open':
      return <Badge colorScheme="green">{overrideLabel ?? formatSizing(action, 'OPEN')}</Badge>;
    case 'bet':
      return <Badge colorScheme="green">{overrideLabel ?? formatSizing(action, 'BET')}</Badge>;
    case 'raise':
      return <Badge colorScheme="purple">{overrideLabel ?? formatSizing(action, 'RAISE')}</Badge>;
    default:
      return <Badge>{action.action.toUpperCase()}</Badge>;
  }
};

const formatSizing = (action: SeatAction, label: string) => {
  if (!action.sizing) {
    return label;
  }
  switch (action.sizing.kind) {
    case 'bucket':
      return `${label} (${action.sizing.key})`;
    case 'pot_ratio':
      return `${label} (${Math.round(action.sizing.value * 100)}%)`;
    case 'bb_multiple':
      return `${label} (${action.sizing.value}x)`;
    case 'label':
      return `${label} (${action.sizing.value})`;
    default:
      return label;
  }
};

const mapChoiceToAction = (
  street: Street,
  choice: ActionChoice,
  sizing: SeatAction['sizing'] | undefined,
  treatRaiseAsOpen: boolean,
): SeatAction | null => {
  switch (choice) {
    case 'check':
      return { action: 'check' };
    case 'limp':
      return { action: 'limp' };
    case 'call':
      return { action: 'call' };
    case 'fold':
      return { action: 'fold' };
    case 'bet':
      return { action: street === 'preflop' ? 'open' : 'bet', sizing };
    case 'raise':
      if (street === 'preflop' && treatRaiseAsOpen) {
        return { action: 'open', sizing };
      }
      return { action: 'raise', sizing };
    default:
      return null;
  }
};

const getOccurrenceIndex = (sequence: StreetActionStep[], stepIndex: number): number => {
  const target = sequence[stepIndex];
  let count = 0;
  for (let i = 0; i <= stepIndex; i += 1) {
    if (sequence[i].seatId === target.seatId) {
      count += 1;
    }
  }
  return count;
};

const findFoldStreetBefore = (seat: SeatState, street: Street): Street | null => {
  const targetIndex = STREET_ORDER.indexOf(street);
  for (let i = 0; i < targetIndex; i += 1) {
    const priorStreet = STREET_ORDER[i];
    const action = seat.actions[priorStreet];
    if (action && action.action === 'fold') {
      return priorStreet;
    }
  }
  return null;
};

const renderBoardCardToken = (card: string) => {
  const rank = card[0] ?? '';
  const suit = card[card.length - 1]?.toLowerCase() ?? '';
  const symbol = SUIT_SYMBOLS[suit] ?? '';
  const palette = SUIT_COLORS[suit] ?? SUIT_COLORS.s;
  return (
    <Box
      key={card}
      borderWidth="1px"
      borderRadius="md"
      px={1.5}
      py={0.5}
      bg="blackAlpha.700"
      borderColor={palette.buttonBorder}
      minW={`${BOARD_CARD_WIDTH}px`}
      textAlign="center"
    >
      <Text fontFamily="mono" fontWeight="semibold" color={palette.defaultText} fontSize="xs">
        {rank}
        {symbol}
      </Text>
    </Box>
  );
};

const ActionMatrixComposer = ({ state, dispatch, bucketOptions }: ActionMatrixComposerProps) => {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const boardModal = useDisclosure();
  const toast = useToast();
  const [editorState, setEditorState] = useState<EditorState | null>(null);
  const [boardEditorState, setBoardEditorState] = useState<BoardEditorState | null>(null);

  const seatMap = useMemo(() => {
    const map = new Map<string, SeatState>();
    state.seats.forEach((seat) => {
      map.set(seat.seatId, seat);
    });
    return map;
  }, [state.seats]);

  const positionSeats = useMemo(() => {
    const seatByPosition = new Map<SeatPosition, SeatState>();
    state.seats.forEach((seat) => {
      if (seat.isActive) {
        seatByPosition.set(seat.position, seat);
      }
    });
    return PRE_FLOP_SEQUENCE_ORDER.map((position) => seatByPosition.get(position)).filter(
      (seat): seat is SeatState => Boolean(seat),
    );
  }, [state.seats]);

  const streetCompletion = useMemo(() => computeStreetCompletion(state), [state.streetSequences, state.stepActions]);

  const currentStreet = useMemo(() => {
    for (const street of STREET_ORDER) {
      if (!streetCompletion[street]) {
        return street;
      }
    }
    return STREET_ORDER[STREET_ORDER.length - 1];
  }, [streetCompletion]);

  const currentStreetIndex = STREET_ORDER.indexOf(currentStreet);

  const potTimeline = useMemo(() => buildPotTimeline(state), [state]);
  const { totalPot, streetStartPot, blindsTotal, actionContext } = potTimeline;

  const openEditor = (step: StreetActionStep, street: Street) => {
    const seat = seatMap.get(step.seatId);
    if (!seat) {
      return;
    }
    const sequence = state.streetSequences[street] ?? [];
    const stepIndex = sequence.findIndex((entry) => entry.id === step.id);
    if (stepIndex === -1) {
      return;
    }

    const snapshot = actionContext.get(step.id);
    const { options, treatRaiseAsOpen } = deriveActionOptions(seat, street, sequence, stepIndex, state.stepActions, snapshot);

    if (options.length === 0) {
      toast({
        title: 'No valid actions available yet.',
        description: 'Finish configuring earlier seats on this street before editing this action.',
        status: 'info',
        duration: 2500,
        isClosable: true,
      });
      return;
    }

    setEditorState({
      step,
      seat,
      street,
      sequence,
      stepIndex,
      options,
      treatRaiseAsOpen,
      potBefore: snapshot?.potBefore ?? 0,
      toCall: snapshot?.toCall ?? 0,
      contribution: snapshot?.contribution ?? 0,
      currentAction: state.stepActions[step.id],
      minRaiseTo: snapshot?.minRaiseTo ?? 0,
      stackBefore: snapshot?.stackBefore ?? seat.startingStack ?? DEFAULT_STACK_SIZE,
      maxContribution:
        snapshot?.maxContribution ??
        (snapshot?.contribution ?? 0) + (snapshot?.stackBefore ?? seat.startingStack ?? DEFAULT_STACK_SIZE),
      currentBet: snapshot?.currentBet ?? 0,
      startingStack: snapshot?.startingStack ?? seat.startingStack ?? DEFAULT_STACK_SIZE,
    });
    onOpen();
  };

  const closeEditor = () => {
    setEditorState(null);
    onClose();
  };

  const openBoardEditor = (street: BoardStreet) => {
    const required = street === 'flop' ? 3 : 1;
    const currentCards = state.board[street] ?? [];
    const disabled = new Set([...state.board.flop, ...state.board.turn, ...state.board.river]);
    currentCards.forEach((card) => disabled.delete(card));
    setBoardEditorState({
      street,
      required,
      selected: new Set(currentCards),
      disabled,
    });
    boardModal.onOpen();
  };

  const closeBoardEditor = () => {
    setBoardEditorState(null);
    boardModal.onClose();
  };

  const handleBoardSave = (street: BoardStreet, cards: string[]) => {
    dispatch({ type: 'set_board_cards', street, cards });
    closeBoardEditor();
  };

  const showPotForStreet = (street: Street) =>
    STREET_ORDER.indexOf(street) <= currentStreetIndex && (streetStartPot[street] ?? 0) > 0;

  const showPotForPosition = currentStreetIndex >= 0 && blindsTotal > 0;
  const showAnyBoard = BOARD_STREETS.some((street) => (state.board[street] ?? []).length > 0);

  return (
    <Stack spacing={4} w="full">
      <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
        <Text fontSize="sm" color="whiteAlpha.700">
          Total pot: {formatBB(totalPot)} {BIG_BLIND_SYMBOL}
        </Text>
        <ButtonGroup size="sm" variant="outline">
          <Tooltip label="Undo">
            <IconButton aria-label="Undo" icon={<RepeatIcon style={{ transform: 'scaleX(-1)' }} />} onClick={() => dispatch({ type: 'undo' })} />
          </Tooltip>
          <Tooltip label="Redo">
            <IconButton aria-label="Redo" icon={<RepeatIcon />} onClick={() => dispatch({ type: 'redo' })} />
          </Tooltip>
          <Tooltip label="Reset table">
            <IconButton aria-label="Reset" icon={<SettingsIcon />} onClick={() => dispatch({ type: 'reset' })} />
          </Tooltip>
        </ButtonGroup>
      </Flex>

      <Flex gap={4} overflowX="auto" overflowY="visible" align="stretch">
        <Stack key="position" spacing={showAnyBoard ? 2 : 0} align="center" minW="140px">
          {showAnyBoard ? (
            <Box
              h={`${BOARD_CARD_ROW_HEIGHT}px`}
              display="flex"
              alignItems="center"
              justifyContent="center"
            />
          ) : null}
          <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" w="full">
            <Table size="sm" variant="simple">
            <Thead>
              <Tr>
                <Th textAlign="center">
                  <Stack spacing={1} align="center">
                    <Text fontWeight="semibold">Position</Text>
                    <Text fontSize="xs" color="whiteAlpha.600" visibility={showPotForPosition ? 'visible' : 'hidden'}>
                      {showPotForPosition ? `${formatBB(blindsTotal)} ${BIG_BLIND_SYMBOL}` : '\u00A0'}
                    </Text>
                  </Stack>
                </Th>
              </Tr>
            </Thead>
            <Tbody>
              {positionSeats.map((seat) => {
                const rawStack = seat.startingStack ?? DEFAULT_STACK_SIZE;
                const adjustedStack =
                  seat.position === 'SB' ? rawStack - 0.5 : seat.position === 'BB' ? rawStack - 1 : rawStack;
                return (
                  <Tr key={seat.seatId}>
                    <Td textAlign="center" height={ROW_HEIGHT} py={2}>
                      <Stack spacing={1} align="center" justify="center" h="full">
                        <Flex justify="center" align="baseline" gap={2}>
                          <Text fontWeight="semibold">{seat.position}</Text>
                          <Text fontSize="0.65rem" color="whiteAlpha.600">
                            ({formatBB(Math.max(adjustedStack, 0))} {BIG_BLIND_SYMBOL})
                          </Text>
                      </Flex>
                        {seat.position === 'SB' && (
                          <Text fontSize="xs" color="whiteAlpha.500">
                            Posts 0.5 {BIG_BLIND_SYMBOL}
                          </Text>
                        )}
                        {seat.position === 'BB' && (
                          <Text fontSize="xs" color="whiteAlpha.500">
                            Posts 1 {BIG_BLIND_SYMBOL}
                          </Text>
                        )}
                      </Stack>
                    </Td>
                  </Tr>
                );
              })}
            </Tbody>
            </Table>
          </Box>
        </Stack>

        {STREET_ORDER.map((street) => {
          const sequence = state.streetSequences[street] ?? [];
          const canEditStreet = isStreetEditable(streetCompletion, street);
          const showPot = showPotForStreet(street);
          const isBoardStreet = street === 'flop' || street === 'turn' || street === 'river';
          const boardCards = isBoardStreet ? state.board[street as BoardStreet] ?? [] : [];
          const showBoard = isBoardStreet && boardCards.length > 0;
          return (
            <Stack key={street} spacing={showBoard || showAnyBoard ? 2 : 0} align="center" minW="160px">
              {(showBoard || showAnyBoard) && (
                <Box
                  h={`${BOARD_CARD_ROW_HEIGHT}px`}
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                >
                  {showBoard ? (
                    <HStack spacing={1.5} align="center">
                      {boardCards.map((card) => renderBoardCardToken(card))}
                      <Button size="xs" variant="link" onClick={() => openBoardEditor(street as BoardStreet)}>
                        Edit
                      </Button>
                    </HStack>
                  ) : null}
                </Box>
              )}
              <Box borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg" w="full">
                <Table size="sm" variant="simple">
                  <Thead>
                    <Tr>
                      <Th textAlign="center">
                        <Stack spacing={1} align="center">
                          <Text fontWeight="semibold">{streetHeader(street)}</Text>
                        <Text fontSize="xs" color="whiteAlpha.600" visibility={showPot ? 'visible' : 'hidden'}>
                          {showPot ? `${formatBB(streetStartPot[street] ?? 0)} ${BIG_BLIND_SYMBOL}` : '\u00A0'}
                        </Text>
                      </Stack>
                    </Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {sequence.length === 0 ? (
                    <Tr>
                      <Td textAlign="center" height={ROW_HEIGHT}>
                        <Stack spacing={1} align="center" justify="center" h="full">
                          <Text color="whiteAlpha.500" fontSize="sm">
                            —
                          </Text>
                        </Stack>
                      </Td>
                    </Tr>
                  ) : (
                    sequence.map((step, index) => {
                      const seat = seatMap.get(step.seatId);
                      if (!seat) {
                        return null;
                      }
                      const action = state.stepActions[step.id];
                      const occurrence = getOccurrenceIndex(sequence, index);
                      const label = occurrence > 1 ? `${seat.position} (${occurrence})` : seat.position;
                      const foldStreet = findFoldStreetBefore(seat, street);
                      const canEditStep = canEditStreet;
                      const snapshot = actionContext.get(step.id);
                      const stackAfter = snapshot?.stackAfter;
                      const contributionBefore = snapshot?.contribution ?? 0;
                      const totalContribution = snapshot?.resultContribution ?? contributionBefore;
                      const addedAmount = snapshot?.resultAdded ?? Math.max(totalContribution - contributionBefore, 0);
                      let badgeOverride: string | undefined;
                      if (action) {
                        if (action.action === 'bet') {
                          if (addedAmount > 0) {
                            badgeOverride = `BET (${formatBB(addedAmount)} ${BIG_BLIND_SYMBOL})`;
                          }
                        } else if (action.action === 'open') {
                          if (totalContribution > 0) {
                            badgeOverride = `OPEN (${formatBB(totalContribution)} ${BIG_BLIND_SYMBOL})`;
                          }
                        } else if (action.action === 'raise') {
                          if (totalContribution > 0) {
                            badgeOverride = `RAISE (to ${formatBB(totalContribution)} ${BIG_BLIND_SYMBOL})`;
                          } else if (addedAmount > 0) {
                            badgeOverride = `RAISE (${formatBB(addedAmount)} ${BIG_BLIND_SYMBOL})`;
                          }
                        }
                      }
                      return (
                        <Tr key={step.id}>
                          <Td textAlign="center" height={ROW_HEIGHT} py={2}>
                            <Stack spacing={1} align="center" justify="center" h="full">
                              <Flex justify="center" align="baseline" gap={2}>
                                <Text fontWeight="semibold">{label}</Text>
                                {action && typeof stackAfter === 'number' && !foldStreet && (
                                  <Text fontSize="0.65rem" color="whiteAlpha.600">
                                    ({formatBB(stackAfter)} {BIG_BLIND_SYMBOL} Behind)
                                  </Text>
                                )}
                              </Flex>
                              {foldStreet ? (
                                <Text fontSize="xs" color="whiteAlpha.500">
                                  Folded {foldStreet.toUpperCase()}
                                </Text>
                              ) : (
                                renderActionBadge(action, badgeOverride)
                              )}
                              {canEditStep && !foldStreet && (
                                <Button size="xs" variant="link" onClick={() => openEditor(step, street)}>
                                  {action ? 'Edit' : 'Edit Action'}
                                </Button>
                              )}
                            </Stack>
                          </Td>
                        </Tr>
                      );
                    })
                  )}
                </Tbody>
                </Table>
              </Box>
            </Stack>
          );
        })}
      </Flex>

      <SeatActionModal
        state={editorState}
        isOpen={isOpen && Boolean(editorState)}
        bucketOptions={bucketOptions}
        onClose={closeEditor}
        onSave={(action) => {
          if (!editorState) {
            return;
          }
          const { street, step, sequence, stepIndex, seat } = editorState;
          const updates: Array<{ stepId: string; action: SeatAction | null }> = [{ stepId: step.id, action }];
          const remove: string[] = [];
          const append: Array<{ seatId: string; afterStepId?: string | null }> = [];

          if (action && action.action === 'fold') {
            for (let i = stepIndex + 1; i < sequence.length; i += 1) {
              const futureStep = sequence[i];
              if (futureStep.seatId === step.seatId) {
                remove.push(futureStep.id);
              }
            }
          }

          if (action && isAggressiveAction(action)) {
            const order = street === 'preflop' ? PRE_FLOP_SEQUENCE_ORDER : POST_FLOP_SEQUENCE_ORDER;
            const positionToSeat = new Map<SeatPosition, SeatState>();
            state.seats.forEach((candidate) => {
              if (candidate.isActive) {
                positionToSeat.set(candidate.position, candidate);
              }
            });

            const seatActionsBefore = new Map<string, SeatAction>();
            sequence.forEach((seqStep, idx) => {
              const existing = idx === stepIndex ? action : state.stepActions[seqStep.id];
              if (existing) {
                seatActionsBefore.set(seqStep.seatId, existing);
              }
            });

            const seatFolded = new Set<string>();
            seatActionsBefore.forEach((act, seatId) => {
              if (act.action === 'fold') {
                seatFolded.add(seatId);
              }
            });

            const currentIndex = order.indexOf(seat.position);
            for (let offset = 1; offset < order.length; offset += 1) {
              const nextPosition = order[(currentIndex + offset) % order.length];
              const nextSeat = positionToSeat.get(nextPosition);
              if (!nextSeat) {
                continue;
              }
              if (seatFolded.has(nextSeat.seatId)) {
                continue;
              }
              const hasFutureStep = sequence.slice(stepIndex + 1).some((seqStep) => seqStep.seatId === nextSeat.seatId);
              if (!hasFutureStep) {
                append.push({ seatId: nextSeat.seatId });
              }
              break;
            }
          }

          dispatch({
            type: 'apply_step_changes',
            street,
            updates,
            append: append.length ? append : undefined,
            remove: remove.length ? remove : undefined,
          });
          closeEditor();
        }}
      />
      <BoardEditorModal
        state={boardEditorState}
        isOpen={boardModal.isOpen && Boolean(boardEditorState)}
        onClose={closeBoardEditor}
        onSave={handleBoardSave}
      />
    </Stack>
  );
};

type SeatActionModalProps = {
  state: EditorState | null;
  isOpen: boolean;
  onClose: () => void;
  bucketOptions: BucketOption[];
  onSave: (action: SeatAction | null) => void;
};

const SeatActionModal = ({ state, isOpen, onClose, bucketOptions, onSave }: SeatActionModalProps) => {
  const toast = useToast();
  const [choice, setChoice] = useState<ActionChoice | ''>('');
  const [betAmount, setBetAmount] = useState<number>(0);

  const minRaiseTo = state?.minRaiseTo ?? 0;
  const isPreflopStreet = state?.street === 'preflop';
  const stackBefore = state?.stackBefore ?? 0;
  const startingStack = state?.startingStack ?? DEFAULT_STACK_SIZE;
  const potBefore = state?.potBefore ?? 0;
  const contribution = state?.contribution ?? 0;
  const toCall = state?.toCall ?? 0;
  const options = state?.options ?? [];
  const editingStreet = state?.street ?? 'preflop';
  const treatRaiseAsOpenFlag = state?.treatRaiseAsOpen ?? false;
  const currentBetValue = state?.currentBet ?? 0;
  const rawMaxContribution = state?.maxContribution ?? Number.POSITIVE_INFINITY;
  const maxContribution =
    Number.isFinite(rawMaxContribution) && rawMaxContribution >= 0
      ? Math.min(contribution + stackBefore, rawMaxContribution)
      : contribution + stackBefore;
  const minRaiseTarget = Math.max(minRaiseTo, contribution + toCall);

  const sliderMax = maxContribution;
  let sliderMin = Math.max(minRaiseTarget, contribution + toCall);
  if (isPreflopStreet && choice === 'call') {
    sliderMin = Math.max(contribution + toCall, 0);
  } else if (!isPreflopStreet) {
    sliderMin = Math.max(sliderMin, 1);
  }
  sliderMin = Math.min(sliderMin, sliderMax);

  const ratioCandidates = useMemo(() => {
    const seen = new Set<number>();
    const values: number[] = [];
    bucketOptions.forEach((option) => {
      const ratio = BUCKET_REPRESENTATIVE_RATIO[option.key];
      if (ratio === undefined || ratio <= 0) {
        return;
      }
      const normalized = Number(ratio.toFixed(2));
      if (seen.has(normalized)) {
        return;
      }
      seen.add(normalized);
      values.push(normalized);
    });
    if (!values.length) {
      const defaults = [0.25, 0.33, 0.5, 0.66, 0.75, 1, 1.25, 1.5, 2, 3];
      return defaults.sort((a, b) => a - b);
    }
    values.sort((a, b) => a - b);
    return values;
  }, [bucketOptions]);

  const clampAmount = useCallback(
    (value: number) => {
      if (!Number.isFinite(value)) {
        return Number(sliderMin.toFixed(2));
      }
      return Number(Math.min(Math.max(value, sliderMin), sliderMax).toFixed(2));
    },
    [sliderMin, sliderMax],
  );

  useEffect(() => {
    if (!state) {
      setChoice('');
      setBetAmount(0);
      return;
    }

    const action = state.currentAction;

    if (!action) {
      setChoice('');
      return;
    }

    switch (action.action) {
      case 'check':
        setChoice('check');
        break;
      case 'limp':
        setChoice('limp');
        break;
      case 'call':
        setChoice('call');
        break;
      case 'fold':
        setChoice('fold');
        break;
      case 'bet':
        setChoice('bet');
        break;
      case 'open':
      case 'raise':
        setChoice('raise');
        break;
      default:
        setChoice('');
        break;
    }
  }, [state]);

  useEffect(() => {
    if (!options.find((option) => option.value === choice)) {
      setChoice('');
    }
  }, [options, choice]);

  useEffect(() => {
    if (!state || (choice !== 'bet' && choice !== 'raise')) {
      return;
    }
    const action = state.currentAction;
    let amount = sliderMin;
    if (action && (action.action === 'bet' || action.action === 'raise' || action.action === 'open')) {
      if (action.sizing?.kind === 'pot_ratio' && typeof action.sizing.value === 'number') {
        amount = potBefore > 0 ? action.sizing.value * potBefore : action.sizing.value;
      } else if (action.sizing?.kind === 'bucket' && action.sizing.key) {
        const mapped = BUCKET_REPRESENTATIVE_RATIO[action.sizing.key];
        if (mapped !== undefined) {
          amount = potBefore > 0 ? mapped * potBefore : mapped;
        }
      } else if (action.sizing?.kind === 'bb_multiple' && typeof action.sizing.value === 'number') {
        amount = action.sizing.value + contribution;
      }
    } else {
      const fallbackRatio = ratioCandidates[0] ?? 0.5;
      const fallbackAmount = potBefore > 0 ? fallbackRatio * potBefore : fallbackRatio;
      amount = Math.max(sliderMin, fallbackAmount);
    }
    setBetAmount(clampAmount(amount));
  }, [state?.step.id, state?.currentAction, choice, clampAmount, sliderMin, ratioCandidates, potBefore, contribution]);

  useEffect(() => {
    if (choice !== 'bet' && choice !== 'raise') {
      return;
    }
    setBetAmount((prev) => clampAmount(prev));
  }, [clampAmount, choice]);

  const sliderDisabled = sliderMax - sliderMin < 1e-6;
  const effectiveBetAmount = sliderDisabled ? sliderMin : clampAmount(betAmount);
  const displayMax = sliderDisabled ? sliderMin : sliderMax;
  const betRatio = potBefore > 0 ? effectiveBetAmount / potBefore : null;

  const handleSave = () => {
    if (!state) {
      onClose();
      return;
    }

    if (!choice) {
      onSave(null);
      return;
    }

    const stackCap = maxContribution;
    let sizing: SeatAction['sizing'] | undefined;
    let plannedContribution: number | null = null;

    if (choice === 'call') {
      const planned = contribution + toCall;
      if (planned > stackCap + 1e-6) {
        toast({
          title: 'Call exceeds remaining stack.',
          description: `${state.seat.position} has ${formatBB(stackBefore)} ${BIG_BLIND_SYMBOL} available.`,
          status: 'warning',
          duration: 2500,
          isClosable: true,
        });
        return;
      }
      plannedContribution = planned;
      // sizing remains undefined for calls
    } else if (choice === 'bet' || choice === 'raise') {
      let amountValue = effectiveBetAmount;
      if (!Number.isFinite(amountValue) || amountValue <= 0) {
        toast({ title: 'Enter a valid bet size.', status: 'warning', duration: 2000, isClosable: true });
        return;
      }
      if (amountValue + 1e-6 < sliderMin) {
        toast({
          title: 'Increase bet size.',
          description: `Bet must reach at least ${formatBB(sliderMin)} ${BIG_BLIND_SYMBOL}.`,
          status: 'warning',
          duration: 2500,
          isClosable: true,
        });
        return;
      }
      if (amountValue > stackCap + 1e-6) {
        toast({
          title: 'Bet exceeds remaining stack.',
          description: `${state.seat.position} has ${formatBB(stackBefore)} ${BIG_BLIND_SYMBOL} available.`,
          status: 'warning',
          duration: 2500,
          isClosable: true,
        });
        return;
      }

      if (isPreflopStreet) {
        if (choice === 'call') {
          sizing = undefined;
          plannedContribution = contribution + toCall;
          amountValue = contribution + toCall;
        } else {
          const incremental = Math.max(amountValue - contribution, 0);
          sizing = { kind: 'bb_multiple', value: incremental };
          plannedContribution = amountValue;
        }
      } else {
        const ratioValue = potBefore > 0 && amountValue > 0 ? amountValue / potBefore : amountValue;
        sizing = { kind: 'pot_ratio', value: ratioValue };
        plannedContribution = amountValue;
      }
    }

    const action = mapChoiceToAction(state.street, choice, sizing, state.treatRaiseAsOpen);
    if (action) {
      let finalContribution = plannedContribution;
      if (finalContribution === null) {
        const result = resolveActionContribution(action, editingStreet, potBefore, contribution, currentBetValue);
        finalContribution = result.newContribution;
      }
      if (finalContribution !== null) {
        const added = Math.max(finalContribution - contribution, 0);
        if (added > stackBefore + 1e-6 || finalContribution > stackCap + 1e-6) {
          toast({
            title: 'Action exceeds remaining stack.',
            description: `${state.seat.position} has ${formatBB(stackBefore)} ${BIG_BLIND_SYMBOL} available.`,
            status: 'warning',
            duration: 2500,
            isClosable: true,
          });
          return;
        }
      }
    }

    onSave(action);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Set Action</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <Stack spacing={4}>
            {state && (
              <Stack spacing={0.5} fontSize="sm" color="whiteAlpha.700">
                <Text>
                  Current pot: {formatBB(state.potBefore ?? 0)} {BIG_BLIND_SYMBOL}
                </Text>
                <Text>
                  Stack remaining: {formatBB(state.stackBefore)} {BIG_BLIND_SYMBOL} (of {formatBB(state.startingStack)} {BIG_BLIND_SYMBOL})
                </Text>
              </Stack>
            )}
            <RadioGroup value={choice} onChange={(value) => setChoice(value as ActionChoice)}>
              <Stack direction="column" spacing={2}>
                {options.map((option) => (
                  <Radio key={option.value} value={option.value}>
                    {option.label}
                  </Radio>
                ))}
              </Stack>
            </RadioGroup>

            {(choice === 'bet' || choice === 'raise') && (
              <Stack spacing={2}>
                <Flex justify="space-between" align="center">
                  <Text fontSize="sm" fontWeight="semibold">
                    {isPreflopStreet ? 'Raise Size' : 'Bet / Raise Size'}
                  </Text>
                  <Text fontSize="sm" fontFamily="mono" color="whiteAlpha.900">
                    {formatBB(effectiveBetAmount)} {BIG_BLIND_SYMBOL}
                  </Text>
                </Flex>
                <Slider
                  value={effectiveBetAmount}
                  min={sliderMin}
                  max={sliderMax}
                  step={1}
                  isDisabled={sliderDisabled}
                  onChange={(value) => setBetAmount(value)}
                >
                  <SliderTrack>
                    <SliderFilledTrack />
                  </SliderTrack>
                  <SliderThumb />
                </Slider>
                <Text fontSize="xs" color="whiteAlpha.600">
                  {formatPotPercentage(betRatio)} of pot · Min {formatBB(sliderMin)} {BIG_BLIND_SYMBOL} · Max {formatBB(displayMax)} {BIG_BLIND_SYMBOL}
                </Text>
              </Stack>
            )}
          </Stack>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            Cancel
          </Button>
          <Button colorScheme="blue" onClick={handleSave}>
            Save
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

type BoardEditorModalProps = {
  state: BoardEditorState | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (street: BoardStreet, cards: string[]) => void;
};

const BoardEditorModal = ({ state, isOpen, onClose, onSave }: BoardEditorModalProps) => {
  const toast = useToast();
  const [selection, setSelection] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (state) {
      setSelection(new Set(state.selected));
    } else {
      setSelection(new Set());
    }
  }, [state, isOpen]);

  if (!state) {
    return null;
  }

  const handleToggle = (card: string) => {
    if (state.disabled.has(card) && !selection.has(card)) {
      return;
    }
    setSelection((prev) => {
      const next = new Set(prev);
      if (next.has(card)) {
        next.delete(card);
        return next;
      }
      if (next.size >= state.required) {
        return next;
      }
      next.add(card);
      return next;
    });
  };

  const handleSave = () => {
    if (selection.size !== state.required) {
      toast({
        title: `Select ${state.required} card${state.required > 1 ? 's' : ''}.`,
        status: 'warning',
        duration: 2000,
        isClosable: true,
      });
      return;
    }
    onSave(state.street, Array.from(selection));
  };

  const streetLabel = state.street === 'flop' ? 'Flop' : state.street === 'turn' ? 'Turn' : 'River';

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Select {streetLabel} Cards</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <Stack spacing={5} align="center">
            <Text fontSize="sm" color="whiteAlpha.700" textAlign="center">
              Choose {state.required} card{state.required > 1 ? 's' : ''} for the {streetLabel.toLowerCase()}.
            </Text>
            <Text fontSize="sm" color="whiteAlpha.600">
              Selected {selection.size} / {state.required}
            </Text>
            <Stack spacing={2} align="center" w="full">
              {BOARD_CARD_SUITS.map((suit) => {
                const palette = SUIT_COLORS[suit] ?? SUIT_COLORS.s;
                return (
                  <SimpleGrid
                    key={suit}
                    columns={13}
                    spacing={1}
                    justifyItems="center"
                    w="full"
                    maxW="520px"
                    mx="auto"
                  >
                    {BOARD_CARD_RANKS.map((rank) => {
                      const card = `${rank}${suit}`;
                      const isSelected = selection.has(card);
                      const disabled = state.disabled.has(card) && !isSelected;
                      return (
                        <Button
                          key={card}
                          size="xs"
                          w="32px"
                          h="28px"
                          borderRadius="sm"
                          bg={isSelected ? palette.selectedBg : palette.buttonBg}
                          borderColor={isSelected ? palette.buttonBorder : 'whiteAlpha.300'}
                          borderWidth="1px"
                          opacity={disabled ? 0.25 : 1}
                          onClick={() => handleToggle(card)}
                          isDisabled={disabled}
                          _hover={
                            disabled
                              ? { cursor: 'not-allowed' }
                              : { bg: palette.selectedBg }
                          }
                          _active={{ bg: palette.selectedBg }}
                          px={0}
                        >
                          <Text
                            fontFamily="mono"
                            fontSize="xs"
                            fontWeight="semibold"
                            color={isSelected ? palette.selectedText : palette.defaultText}
                          >
                            {rank}
                            {SUIT_SYMBOLS[suit]}
                          </Text>
                        </Button>
                      );
                    })}
                  </SimpleGrid>
                );
              })}
            </Stack>
          </Stack>
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            Cancel
          </Button>
          <Button colorScheme="blue" onClick={handleSave}>
            Save
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};

export default ActionMatrixComposer;
