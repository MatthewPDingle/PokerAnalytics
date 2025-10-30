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
  NumberDecrementStepper,
  NumberIncrementStepper,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  Radio,
  RadioGroup,
  Select,
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
import { Dispatch, useEffect, useMemo, useState } from 'react';

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
};

type ActionSnapshot = {
  potBefore: number;
  toCall: number;
  contribution: number;
  minRaiseTo: number;
};

type PotTimeline = {
  actionContext: Map<string, ActionSnapshot>;
  totalPot: number;
  streetStartPot: Record<Street, number>;
  blindsTotal: number;
};

const PRE_FLOP_RAISE_MULTIPLES: number[] = [2, 2.5, 3, 3.5, 4, 5, 6, 7, 8, 10];
const DEFAULT_PRE_FLOP_MULTIPLE = 3;

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
const OPTION_LABEL_WIDTH = 8;

const formatMultipleValue = (value: number): string => (Math.abs(value - Math.round(value)) < 1e-6 ? value.toFixed(0) : value.toFixed(1));

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

  const smallBlindSeat = state.seats.find((seat) => seat.isActive && seat.position === 'SB');
  if (smallBlindSeat) {
    contributions.preflop.set(smallBlindSeat.seatId, 0.5);
    pot += 0.5;
  }

  const bigBlindSeat = state.seats.find((seat) => seat.isActive && seat.position === 'BB');
  if (bigBlindSeat) {
    contributions.preflop.set(bigBlindSeat.seatId, (contributions.preflop.get(bigBlindSeat.seatId) ?? 0) + 1);
    pot += 1;
  }

  blindsTotal = pot;
  streetStartPot.preflop = pot;

  STREET_ORDER.forEach((street) => {
    if (street !== 'preflop') {
      streetStartPot[street] = pot;
    }
    const sequence = state.streetSequences[street] ?? [];
    let currentBet = street === 'preflop' ? 1 : 0;
    let lastRaiseAmount = 1;
    const streetContributions = contributions[street];
    sequence.forEach((step) => {
      const contribution = streetContributions.get(step.seatId) ?? 0;
      const toCall = Math.max(currentBet - contribution, 0);
      actionContext.set(step.id, {
        potBefore: pot,
        toCall,
        contribution,
        minRaiseTo: currentBet + Math.max(lastRaiseAmount, 1),
      });

      const action = state.stepActions[step.id];
      if (!action) {
        return;
      }
      const previousBet = currentBet;
      const result = resolveActionContribution(action, street, pot, contribution, currentBet);
      pot += result.added;
      streetContributions.set(step.seatId, result.newContribution);
      currentBet = Math.max(currentBet, result.newBet);
      if (result.newBet > previousBet) {
        lastRaiseAmount = Math.max(result.newBet - previousBet, 1);
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

const padLabel = (value: string, length: number) => {
  if (value.length >= length) {
    return value;
  }
  return value + '\u00A0'.repeat(length - value.length);
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

const renderActionBadge = (action?: SeatAction) => {
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
      return <Badge colorScheme="green">{formatSizing(action, 'OPEN')}</Badge>;
    case 'bet':
      return <Badge colorScheme="green">{formatSizing(action, 'BET')}</Badge>;
    case 'raise':
      return <Badge colorScheme="purple">{formatSizing(action, 'RAISE')}</Badge>;
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

const ActionMatrixComposer = ({ state, dispatch, bucketOptions }: ActionMatrixComposerProps) => {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();
  const [editorState, setEditorState] = useState<EditorState | null>(null);

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
    });
    onOpen();
  };

  const closeEditor = () => {
    setEditorState(null);
    onClose();
  };

  const showPotForStreet = (street: Street) =>
    STREET_ORDER.indexOf(street) <= currentStreetIndex && (streetStartPot[street] ?? 0) > 0;

  const showPotForPosition = currentStreetIndex >= 0 && blindsTotal > 0;

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

      <Flex gap={4} overflowX="auto" align="stretch">
        <Box minW="140px" borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg">
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
              {positionSeats.map((seat) => (
                <Tr key={seat.seatId}>
                  <Td textAlign="center" height={ROW_HEIGHT} py={2}>
                    <Stack spacing={1} align="center" justify="center" h="full">
                      <Text fontWeight="semibold">{seat.position}</Text>
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
              ))}
            </Tbody>
          </Table>
        </Box>

        {STREET_ORDER.map((street) => {
          const sequence = state.streetSequences[street] ?? [];
          const canEditStreet = isStreetEditable(streetCompletion, street);
          const showPot = showPotForStreet(street);
          return (
            <Box key={street} minW="160px" borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg">
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
                      return (
                        <Tr key={step.id}>
                          <Td textAlign="center" height={ROW_HEIGHT} py={2}>
                            <Stack spacing={1} align="center" justify="center" h="full">
                              <Text fontWeight="semibold">{label}</Text>
                              {foldStreet ? (
                                <Text fontSize="xs" color="whiteAlpha.500">
                                  Folded {foldStreet.toUpperCase()}
                                </Text>
                              ) : (
                                renderActionBadge(action)
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
  const [selectedMultiple, setSelectedMultiple] = useState<string>(() => String(DEFAULT_PRE_FLOP_MULTIPLE));
  const [customMultiple, setCustomMultiple] = useState<string>(() => String(DEFAULT_PRE_FLOP_MULTIPLE));
  const [selectedRatio, setSelectedRatio] = useState<string>('0.50');
  const [customRatio, setCustomRatio] = useState<string>('0.50');
  const minRaiseTo = state?.minRaiseTo ?? 0;
  const isPreflopStreet = state?.street === 'preflop';

  const availableRaiseMultiples = useMemo(() => {
    if (!isPreflopStreet) {
      return PRE_FLOP_RAISE_MULTIPLES;
    }
    const required = Math.max(minRaiseTo, 0);
    const baseline = PRE_FLOP_RAISE_MULTIPLES.filter((value) => value + 1e-6 >= Math.max(required, 2));
    if (required > 0 && !baseline.some((value) => Math.abs(value - required) < 1e-6)) {
      baseline.push(required);
    }
    const unique = Array.from(new Set(baseline.map((value) => Number(value.toFixed(2)))));
    return unique.sort((a, b) => a - b);
  }, [isPreflopStreet, minRaiseTo]);

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

  useEffect(() => {
    if (!state) {
      setChoice('');
      setSelectedMultiple(() => String(DEFAULT_PRE_FLOP_MULTIPLE));
      setCustomMultiple(() => String(DEFAULT_PRE_FLOP_MULTIPLE));
      setSelectedRatio('0.50');
      setCustomRatio('0.50');
      return;
    }

    const { street, currentAction } = state;
    const action = currentAction;

    if (!action) {
      setChoice('');
      if (isPreflopStreet) {
        const defaultMultiple = availableRaiseMultiples[0] ?? DEFAULT_PRE_FLOP_MULTIPLE;
        const adjusted = Math.max(defaultMultiple, minRaiseTo || DEFAULT_PRE_FLOP_MULTIPLE);
        setSelectedMultiple(String(adjusted));
        setCustomMultiple(String(adjusted));
      } else {
        const potBefore = state.potBefore ?? 0;
        const minRaiseTarget = Math.max(minRaiseTo, (state.contribution ?? 0) + (state.toCall ?? 0));
        const effectiveRatios = ratioCandidates;
        if (potBefore > 0) {
          const neededRatio = minRaiseTarget > 0 ? minRaiseTarget / potBefore : 0;
          const filtered = effectiveRatios.filter((ratio) => ratio * potBefore + 1e-6 >= minRaiseTarget);
          if (filtered.length) {
            const fallback = filtered[0];
            setSelectedRatio(fallback.toFixed(2));
            setCustomRatio(fallback.toFixed(2));
          } else {
            const fallback = neededRatio > 0 ? neededRatio : effectiveRatios[0] ?? 0.5;
            setSelectedRatio('other');
            setCustomRatio(fallback.toFixed(2));
          }
        } else {
          const fallback = effectiveRatios[0] ?? 0.5;
          setSelectedRatio(fallback.toFixed(2));
          setCustomRatio(fallback.toFixed(2));
        }
      }
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
      case 'open':
      case 'bet':
      case 'raise':
        setChoice('raise');
        break;
      default:
        setChoice('');
        break;
    }

    if (isPreflopStreet && action.sizing?.kind === 'bb_multiple' && typeof action.sizing.value === 'number') {
      const value = action.sizing.value;
      const matched = availableRaiseMultiples.find((entry) => Math.abs(entry - value) < 1e-6);
      if (matched !== undefined) {
        setSelectedMultiple(String(matched));
        setCustomMultiple(String(matched));
      } else {
        setSelectedMultiple('other');
        setCustomMultiple(String(value));
      }
    } else {
      setSelectedMultiple(() => String(DEFAULT_PRE_FLOP_MULTIPLE));
      setCustomMultiple(() => String(DEFAULT_PRE_FLOP_MULTIPLE));
    }

    if (!isPreflopStreet) {
      const potBefore = state.potBefore ?? 0;
      const minRaiseTarget = Math.max(minRaiseTo, (state.contribution ?? 0) + (state.toCall ?? 0));
      const effectiveRatios = ratioCandidates;
      let ratioValue: number | null = null;
      if (action.sizing?.kind === 'pot_ratio' && typeof action.sizing.value === 'number') {
        ratioValue = action.sizing.value;
      } else if (action.sizing?.kind === 'bucket' && action.sizing.key) {
        const mapped = BUCKET_REPRESENTATIVE_RATIO[action.sizing.key];
        if (mapped !== undefined) {
          ratioValue = mapped;
        }
      }

      if (ratioValue !== null) {
        const matched = effectiveRatios.find((ratio) => Math.abs(ratio - ratioValue!) < 1e-6);
        if (matched !== undefined) {
          const normalized = matched.toFixed(2);
          setSelectedRatio(normalized);
          setCustomRatio(normalized);
        } else {
          setSelectedRatio('other');
          setCustomRatio(ratioValue.toFixed(2));
        }
      } else if (potBefore > 0) {
        const filtered = effectiveRatios.filter((ratio) => ratio * potBefore + 1e-6 >= minRaiseTarget);
        if (filtered.length) {
          const fallback = filtered[0];
          setSelectedRatio(fallback.toFixed(2));
          setCustomRatio(fallback.toFixed(2));
        } else {
          const fallback = minRaiseTarget > 0 ? minRaiseTarget / potBefore : effectiveRatios[0] ?? 0.5;
          setSelectedRatio('other');
          setCustomRatio(fallback.toFixed(2));
        }
      } else {
        const fallback = effectiveRatios[0] ?? 0.5;
        setSelectedRatio(fallback.toFixed(2));
        setCustomRatio(fallback.toFixed(2));
      }
    }
  }, [state, availableRaiseMultiples, ratioCandidates, minRaiseTo, isPreflopStreet]);

  const options = state?.options ?? [];
  const potBefore = state?.potBefore ?? 0;
  const toCall = state?.toCall ?? 0;
  const contribution = state?.contribution ?? 0;
  const minRaiseTarget = Math.max(minRaiseTo, contribution + toCall);
  const requiresSizing = choice === 'bet' || choice === 'raise';
  const showPreflopSizing = Boolean(isPreflopStreet && requiresSizing);
  const showPostflopSizing = Boolean(!isPreflopStreet && requiresSizing);

  const availableRatios = useMemo(() => {
    if (isPreflopStreet || potBefore <= 0) {
      return ratioCandidates;
    }
    const filtered = ratioCandidates.filter((ratio) => ratio * potBefore + 1e-6 >= minRaiseTarget);
    return filtered.length ? filtered : ratioCandidates;
  }, [isPreflopStreet, ratioCandidates, potBefore, minRaiseTarget]);

  useEffect(() => {
    if (!options.find((option) => option.value === choice)) {
      setChoice('');
    }
  }, [options, choice]);

  const computeRatioForMultiple = (multiple: number): number | null => {
    if (potBefore <= 0) {
      return null;
    }
    return Math.max(multiple - contribution, 0) / potBefore;
  };

  const formatMultipleOptionLabel = (multiple: number) =>
    `${padLabel(`${formatMultipleValue(multiple)}x`, OPTION_LABEL_WIDTH)} (${formatPotPercentage(computeRatioForMultiple(multiple))})`;

  const formatRatioOptionLabel = (ratio: number) => {
    const amount = potBefore > 0 ? ratio * potBefore : ratio;
    const label = potBefore > 0 ? `${formatBB(amount)} BB` : `${ratio.toFixed(2)}x`;
    return `${padLabel(label, OPTION_LABEL_WIDTH + 3)} (${formatPotPercentage(ratio)})`;
  };

  const customMultipleValue = parseFloat(customMultiple);
  const customMultipleLabel =
    selectedMultiple === 'other'
      ? Number.isFinite(customMultipleValue)
        ? `${padLabel(`${formatMultipleValue(customMultipleValue)}x`, OPTION_LABEL_WIDTH)} (${formatPotPercentage(computeRatioForMultiple(customMultipleValue))})`
        : 'Enter a size'
      : '';

  const customRatioValue = parseFloat(customRatio);
  const customRatioLabel =
    selectedRatio === 'other'
      ? Number.isFinite(customRatioValue)
        ? formatRatioOptionLabel(customRatioValue)
        : 'Enter a size'
      : '';

  const handleSave = () => {
    if (!state) {
      onClose();
      return;
    }

    if (!choice) {
      onSave(null);
      return;
    }

    let sizing: SeatAction['sizing'] | undefined;

    if (requiresSizing) {
      if (showPreflopSizing) {
        const rawValue = selectedMultiple === 'other' ? parseFloat(customMultiple) : parseFloat(selectedMultiple);
        if (!Number.isFinite(rawValue) || rawValue <= 0) {
          toast({ title: 'Enter a valid raise size.', status: 'warning', duration: 2000, isClosable: true });
          return;
        }
        const minRaiseTarget = Math.max(state.minRaiseTo ?? 0, contribution + toCall);
        if (rawValue + 1e-6 < minRaiseTarget) {
          toast({
            title: 'Increase raise size.',
            description: `Raise must reach at least ${formatBB(minRaiseTarget)} ${BIG_BLIND_SYMBOL}.`,
            status: 'warning',
            duration: 2500,
            isClosable: true,
          });
          return;
        }
        sizing = { kind: 'bb_multiple', value: rawValue };
      } else {
        const ratioValue = selectedRatio === 'other' ? parseFloat(customRatio) : parseFloat(selectedRatio);
        if (!Number.isFinite(ratioValue) || ratioValue <= 0) {
          toast({ title: 'Enter a valid bet size.', status: 'warning', duration: 2000, isClosable: true });
          return;
        }
        if (potBefore > 0 && ratioValue * potBefore + 1e-6 < minRaiseTarget) {
          toast({
            title: 'Increase bet size.',
            description: `Bet must reach at least ${formatBB(minRaiseTarget)} ${BIG_BLIND_SYMBOL}.`,
            status: 'warning',
            duration: 2500,
            isClosable: true,
          });
          return;
        }
        sizing = { kind: 'pot_ratio', value: ratioValue };
      }
    }

    const action = mapChoiceToAction(state.street, choice, sizing, state.treatRaiseAsOpen);
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
              <Text fontSize="sm" color="whiteAlpha.700">
                Current pot: {formatBB(state.potBefore ?? 0)} {BIG_BLIND_SYMBOL}
              </Text>
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

            {showPreflopSizing && (
              <Stack spacing={2}>
                <Text fontSize="sm" fontWeight="semibold">
                  Raise Size
                </Text>
                <Select
                  value={selectedMultiple}
                  onChange={(event) => {
                    const value = event.target.value;
                    setSelectedMultiple(value);
                    if (value !== 'other') {
                      setCustomMultiple(value);
                    }
                  }}
                  fontFamily="mono"
                >
                  {availableRaiseMultiples.map((value) => (
                    <option key={value} value={value}>
                      {formatMultipleOptionLabel(value)}
                    </option>
                  ))}
                  <option value="other">Other…</option>
                </Select>
                {selectedMultiple === 'other' && (
                  <NumberInput
                    value={customMultiple}
                    onChange={(value) => setCustomMultiple(value)}
                    min={Math.max(minRaiseTarget, 0)}
                    precision={2}
                    step={0.5}
                  >
                    <NumberInputField placeholder="Raise multiple" />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                )}
                {customMultipleLabel && (
                  <Text fontSize="xs" color="whiteAlpha.600">
                    {customMultipleLabel}
                  </Text>
                )}
              </Stack>
            )}

            {showPostflopSizing && (
              <Stack spacing={2}>
                <Text fontSize="sm" fontWeight="semibold">
                  Bet / Raise Size
                </Text>
                <Select
                  value={selectedRatio}
                  onChange={(event) => {
                    const value = event.target.value;
                    setSelectedRatio(value);
                    if (value !== 'other') {
                      const numeric = Number.parseFloat(value);
                      setCustomRatio(Number.isFinite(numeric) ? numeric.toFixed(2) : value);
                    }
                  }}
                  fontFamily="mono"
                >
                  {availableRatios.map((ratio) => {
                    const value = ratio.toFixed(2);
                    return (
                      <option key={value} value={value}>
                        {formatRatioOptionLabel(ratio)}
                      </option>
                    );
                  })}
                  <option value="other">Other…</option>
                </Select>
                {selectedRatio === 'other' && (
                  <NumberInput
                    value={customRatio}
                    onChange={(value) => setCustomRatio(value)}
                    min={potBefore > 0 ? Math.max(minRaiseTarget / potBefore, 0) : 0}
                    precision={2}
                    step={0.05}
                  >
                    <NumberInputField placeholder="Pot multiple" />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                )}
                {customRatioLabel && (
                  <Text fontSize="xs" color="whiteAlpha.600">
                    {customRatioLabel}
                  </Text>
                )}
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

export default ActionMatrixComposer;
