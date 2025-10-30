import { Reducer } from 'react';

/**
 * Table-based hand composer for the Line Explorer.
 *
 * Each seat represents a position at the poker table. Users assign actions
 * street-by-street (preflop → river). The aggregate of those actions forms
 * the descriptor used to query backend aggregates.
 */

export type Street = 'preflop' | 'flop' | 'turn' | 'river';
export const STREET_ORDER: Street[] = ['preflop', 'flop', 'turn', 'river'];

export type SeatPosition =
  | 'SB'
  | 'BB'
  | 'UTG'
  | 'UTG+1'
  | 'UTG+2'
  | 'UTG+3'
  | 'LJ'
  | 'HJ'
  | 'CO'
  | 'BTN';

export type ActionType =
  | 'fold'
  | 'check'
  | 'call'
  | 'bet'
  | 'raise'
  | 'open'
  | 'limp'
  | 'all_in';

export type ActionSizing =
  | { kind: 'pot_ratio'; value: number }
  | { kind: 'bb_multiple'; value: number }
  | { kind: 'label'; value: string }
  | { kind: 'bucket'; key: string };

export type SeatAction = {
  action: ActionType;
  sizing?: ActionSizing;
  notes?: string;
};

export type SeatState = {
  seatId: string;
  position: SeatPosition;
  isActive: boolean;
  actions: Partial<Record<Street, SeatAction>>;
};

export type StreetActionStep = {
  id: string;
  seatId: string;
};

export type TableComposerState = {
  seats: SeatState[];
  buttonSeatId: string | null;
  focalSeatId: string | null;
  focalStreet: Street;
  flopTextureKeys: string[];
  excludeHero: boolean;
  tableSize: number;
  history: TableComposerSnapshot[];
  future: TableComposerSnapshot[];
  streetSequences: Record<Street, StreetActionStep[]>;
  stepActions: Record<string, SeatAction>;
  nextStepId: number;
};

export type TableComposerSnapshot = Omit<TableComposerState, 'history' | 'future'>;

export type TableComposerAction =
  | { type: 'toggle_seat_active'; seatId: string }
  | { type: 'set_button'; seatId: string }
  | { type: 'set_action'; seatId: string; street: Street; action: SeatAction | null }
  | { type: 'set_seat_actions'; seatId: string; actions: Partial<Record<Street, SeatAction>> }
  | { type: 'set_focal'; seatId: string | null; street?: Street }
  | { type: 'set_flop_textures'; keys: string[] }
  | { type: 'set_exclude_hero'; exclude: boolean }
  | { type: 'set_table_size'; size: number }
  | { type: 'apply_actions'; items: Array<{ seatId: string; street: Street; action: SeatAction | null }> }
  | {
      type: 'apply_step_changes';
      street: Street;
      updates?: Array<{ stepId: string; action: SeatAction | null }>;
      append?: Array<{ seatId: string; afterStepId?: string | null }>;
      remove?: string[];
    }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'reset'; preset?: TableComposerPreset };

export type TableComposerPreset = {
  seats: SeatState[];
  buttonSeatId: string | null;
};

const DEFAULT_SEAT_ORDER: SeatPosition[] = ['SB', 'BB', 'UTG', 'UTG+1', 'UTG+2', 'UTG+3', 'LJ', 'HJ', 'CO', 'BTN'];
const MIN_TABLE_SIZE = 2;
const MAX_TABLE_SIZE = DEFAULT_SEAT_ORDER.length;
const DEFAULT_TABLE_SIZE = 6;
const REMOVAL_PRIORITY: SeatPosition[] = ['UTG+1', 'UTG+2', 'UTG+3', 'LJ', 'UTG', 'HJ', 'CO', 'BTN'];

export const PRE_FLOP_SEQUENCE_ORDER: SeatPosition[] = ['UTG', 'UTG+1', 'UTG+2', 'UTG+3', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB'];
export const POST_FLOP_SEQUENCE_ORDER: SeatPosition[] = ['SB', 'BB', 'UTG', 'UTG+1', 'UTG+2', 'UTG+3', 'LJ', 'HJ', 'CO', 'BTN'];

const DEFAULT_PRESET: TableComposerPreset = {
  seats: DEFAULT_SEAT_ORDER.map((position) => ({
    seatId: `seat-${position}`,
    position,
    isActive: true,
    actions: {},
  })),
  buttonSeatId: 'seat-BTN',
};

const cloneSeatAction = (action: SeatAction): SeatAction => ({
  action: action.action,
  sizing: action.sizing
    ? action.sizing.kind === 'bucket'
      ? { kind: 'bucket', key: action.sizing.key }
      : action.sizing.kind === 'pot_ratio'
        ? { kind: 'pot_ratio', value: action.sizing.value }
        : action.sizing.kind === 'bb_multiple'
          ? { kind: 'bb_multiple', value: action.sizing.value }
          : { kind: 'label', value: action.sizing.value }
    : undefined,
  notes: action.notes,
});

const cloneStepActions = (stepActions: Record<string, SeatAction>): Record<string, SeatAction> =>
  Object.fromEntries(Object.entries(stepActions).map(([stepId, action]) => [stepId, cloneSeatAction(action)]));

const cloneSequences = (sequences: Record<Street, StreetActionStep[]>): Record<Street, StreetActionStep[]> => {
  const result: Record<Street, StreetActionStep[]> = {
    preflop: [],
    flop: [],
    turn: [],
    river: [],
  };
  STREET_ORDER.forEach((street) => {
    result[street] = sequences[street]?.map((step) => ({ ...step })) ?? [];
  });
  return result;
};

const createStepId = (counter: number): string => `step-${counter}`;

const cloneSeats = (seats: SeatState[]): SeatState[] =>
  seats.map((seat) => ({
    ...seat,
    actions: { ...seat.actions },
  }));

const orderSeatsByPositions = (seats: SeatState[], order: SeatPosition[]): SeatState[] => {
  const seatMap = new Map<SeatPosition, SeatState>();
  seats.forEach((seat) => {
    if (seat.isActive) {
      seatMap.set(seat.position, seat);
    }
  });
  return order.map((position) => seatMap.get(position)).filter((seat): seat is SeatState => Boolean(seat));
};

const buildInitialSequences = (seats: SeatState[], createId: () => string): Record<Street, StreetActionStep[]> => ({
  preflop: orderSeatsByPositions(seats, PRE_FLOP_SEQUENCE_ORDER).map((seat) => ({
    id: createId(),
    seatId: seat.seatId,
  })),
  flop: [],
  turn: [],
  river: [],
});

const pruneSequencesForActiveSeats = (
  sequences: Record<Street, StreetActionStep[]>,
  stepActions: Record<string, SeatAction>,
  seats: SeatState[],
): { sequences: Record<Street, StreetActionStep[]>; stepActions: Record<string, SeatAction> } => {
  const activeSeatIds = new Set(seats.filter((seat) => seat.isActive).map((seat) => seat.seatId));
  const updatedSequences: Record<Street, StreetActionStep[]> = {
    preflop: [],
    flop: [],
    turn: [],
    river: [],
  };
  const updatedActions = { ...stepActions };
  STREET_ORDER.forEach((street) => {
    const retained: StreetActionStep[] = [];
    sequences[street]?.forEach((step) => {
      if (activeSeatIds.has(step.seatId)) {
        retained.push({ ...step });
      } else if (updatedActions[step.id]) {
        delete updatedActions[step.id];
      }
    });
    updatedSequences[street] = retained;
  });
  return { sequences: updatedSequences, stepActions: updatedActions };
};

const ensurePreflopCoverage = (
  sequences: Record<Street, StreetActionStep[]>,
  seats: SeatState[],
  stepActions: Record<string, SeatAction>,
  createId: () => string,
) => {
  const activeSeats = orderSeatsByPositions(seats, PRE_FLOP_SEQUENCE_ORDER);
  const existingSteps = sequences.preflop ?? [];
  const reuseMap = new Map<string, StreetActionStep[]>();
  existingSteps.forEach((step) => {
    const list = reuseMap.get(step.seatId) ?? [];
    list.push(step);
    reuseMap.set(step.seatId, list);
  });
  const rebuilt: StreetActionStep[] = activeSeats.map((seat) => {
    const list = reuseMap.get(seat.seatId);
    if (list && list.length) {
      return list.shift()!;
    }
    return { id: createId(), seatId: seat.seatId };
  });
  reuseMap.forEach((list) => {
    list.forEach((step) => delete stepActions[step.id]);
  });
  sequences.preflop = rebuilt;
};

const isAggressiveStepAction = (action?: SeatAction): boolean => {
  if (!action) {
    return false;
  }
  return action.action === 'open' || action.action === 'bet' || action.action === 'raise';
};

const syncSeatActionsWithSteps = (
  seats: SeatState[],
  sequences: Record<Street, StreetActionStep[]>,
  stepActions: Record<string, SeatAction>,
): SeatState[] =>
  seats.map((seat) => {
    const actions: Partial<Record<Street, SeatAction>> = {};
    STREET_ORDER.forEach((street) => {
      const steps = sequences[street] ?? [];
      steps.forEach((step) => {
        if (step.seatId !== seat.seatId) {
          return;
        }
        const action = stepActions[step.id];
        if (action) {
          actions[street] = cloneSeatAction(action);
        }
      });
    });
    return {
      ...seat,
      actions,
    };
  });

const hasContinuingAction = (
  sequences: Record<Street, StreetActionStep[]>,
  stepActions: Record<string, SeatAction>,
  seatId: string,
  street: Street,
): boolean => {
  if (street === 'preflop') {
    return true;
  }
  const targetIndex = STREET_ORDER.indexOf(street);
  if (targetIndex <= 0) {
    return true;
  }
  for (let i = 0; i < targetIndex; i += 1) {
    const priorStreet = STREET_ORDER[i];
    const sequence = sequences[priorStreet] ?? [];
    let lastStep: StreetActionStep | null = null;
    for (let j = sequence.length - 1; j >= 0; j -= 1) {
      if (sequence[j].seatId === seatId) {
        lastStep = sequence[j];
        break;
      }
    }
    if (!lastStep) {
      return false;
    }
    const action = stepActions[lastStep.id];
    if (!action || action.action === 'fold') {
      return false;
    }
    const index = sequence.indexOf(lastStep);
    for (let j = index + 1; j < sequence.length; j += 1) {
      if (!stepActions[sequence[j].id]) {
        return false;
      }
    }
  }
  return true;
};

const streetIsClosed = (
  sequences: Record<Street, StreetActionStep[]>,
  stepActions: Record<string, SeatAction>,
  street: Street,
): boolean => {
  const sequence = sequences[street] ?? [];
  if (!sequence.length) {
    return false;
  }
  return sequence.every((step) => Boolean(stepActions[step.id]));
};

const isSeatEligibleForStreet = (
  sequences: Record<Street, StreetActionStep[]>,
  stepActions: Record<string, SeatAction>,
  seatId: string,
  street: Street,
): boolean => {
  const targetIndex = STREET_ORDER.indexOf(street);
  if (targetIndex <= 0) {
    return true;
  }
  const priorStreet = STREET_ORDER[targetIndex - 1];
  if (!streetIsClosed(sequences, stepActions, priorStreet)) {
    return false;
  }
  return hasContinuingAction(sequences, stepActions, seatId, street);
};

const ensurePriorStepsFilled = (
  sequence: StreetActionStep[],
  targetIndex: number,
  stepActions: Record<string, SeatAction>,
) => {
  for (let i = 0; i < targetIndex; i += 1) {
    const prior = sequence[i];
    if (!stepActions[prior.id]) {
      stepActions[prior.id] = { action: 'fold' };
    }
  }
};

const ensurePostFlopEligibility = (
  sequences: Record<Street, StreetActionStep[]>,
  seats: SeatState[],
  stepActions: Record<string, SeatAction>,
  createId: () => string,
  completionMap: Record<Street, boolean>,
) => {
  STREET_ORDER.forEach((street, index) => {
    if (index === 0) {
      return;
    }
    const previousComplete = STREET_ORDER.slice(0, index).every((prior) => completionMap[prior]);
    if (!previousComplete) {
      const existingSteps = sequences[street] ?? [];
      existingSteps.forEach((step) => delete stepActions[step.id]);
      sequences[street] = [];
      return;
    }
    const order = POST_FLOP_SEQUENCE_ORDER;
    const eligibleSeats = orderSeatsByPositions(
      seats.filter((seat) => seat.isActive && isSeatEligibleForStreet(sequences, stepActions, seat.seatId, street)),
      order,
    );
    if (eligibleSeats.length <= 1) {
      const existingSteps = sequences[street] ?? [];
      existingSteps.forEach((step) => {
        delete stepActions[step.id];
      });
      sequences[street] = [];
      return;
    }
    const existingSequence = sequences[street] ?? [];
    const filtered = existingSequence.filter((step) => {
      if (eligibleSeats.some((seat) => seat.seatId === step.seatId)) {
        return true;
      }
      delete stepActions[step.id];
      return false;
    });
    const missing = new Set(eligibleSeats.map((seat) => seat.seatId));
    filtered.forEach((step) => {
      if (missing.has(step.seatId)) {
        missing.delete(step.seatId);
      }
    });
    const additions: StreetActionStep[] = [];
    eligibleSeats.forEach((seat) => {
      if (missing.has(seat.seatId)) {
        additions.push({ id: createId(), seatId: seat.seatId });
      }
    });
    sequences[street] = [...filtered, ...additions];
  });
};

const ensureContinuationSteps = (
  street: Street,
  sequences: Record<Street, StreetActionStep[]>,
  stepActions: Record<string, SeatAction>,
  seats: SeatState[],
  createId: () => string,
) => {
  const sequence = sequences[street];
  if (!sequence || sequence.length === 0) {
    return;
  }
  const order = street === 'preflop' ? PRE_FLOP_SEQUENCE_ORDER : POST_FLOP_SEQUENCE_ORDER;
  const eligibleSeats =
    street === 'preflop'
      ? orderSeatsByPositions(seats, order)
      : orderSeatsByPositions(
          seats.filter((seat) => seat.isActive && isSeatEligibleForStreet(sequences, stepActions, seat.seatId, street)),
          order,
        );
  if (!eligibleSeats.length) {
    return;
  }

  const lastActionBySeat = new Map<string, SeatAction | undefined>();
  sequence.forEach((step) => {
    const action = stepActions[step.id];
    if (action) {
      lastActionBySeat.set(step.seatId, action);
    }
  });

  const aliveSeats = eligibleSeats.filter((seat) => {
    const lastAction = lastActionBySeat.get(seat.seatId);
    return !lastAction || lastAction.action !== 'fold';
  });

  if (aliveSeats.length <= 1) {
    return;
  }

  let lastAggIndex = -1;
  let lastAggSeatId: string | null = null;
  sequence.forEach((step, index) => {
    const action = stepActions[step.id];
    if (isAggressiveStepAction(action)) {
      lastAggIndex = index;
      lastAggSeatId = step.seatId;
    }
  });

  if (lastAggIndex === -1 || !lastAggSeatId) {
    return;
  }

  const aggressorIndex = eligibleSeats.findIndex((seat) => seat.seatId === lastAggSeatId);
  if (aggressorIndex === -1) {
    return;
  }

  const tail = sequence.slice(lastAggIndex + 1);

  for (let offset = 1; offset < eligibleSeats.length; offset += 1) {
    const seat = eligibleSeats[(aggressorIndex + offset) % eligibleSeats.length];
    if (!seat || seat.seatId === lastAggSeatId) {
      break;
    }
    const lastAction = lastActionBySeat.get(seat.seatId);
    if (lastAction && lastAction.action === 'fold') {
      continue;
    }
    const existingStep = tail.find((step) => step.seatId === seat.seatId);
    if (!existingStep) {
      sequence.push({ id: createId(), seatId: seat.seatId });
      return;
    }
    const existingAction = stepActions[existingStep.id];
    if (!existingAction) {
      return;
    }
    if (existingAction.action === 'fold') {
      continue;
    }
    if (isAggressiveStepAction(existingAction)) {
      return;
    }
  }

  if (lastAggSeatId === null && eligibleSeats.length > 0) {
    const lastStep = sequence[sequence.length - 1];
    if (!lastStep) {
      return;
    }
    const currentIndex = eligibleSeats.findIndex((seat) => seat.seatId === lastStep.seatId);
    if (currentIndex === -1) {
      return;
    }
    const finalSeat = eligibleSeats[eligibleSeats.length - 1];
    if (lastStep.seatId === finalSeat.seatId) {
      return;
    }
    const nextSeat = eligibleSeats[currentIndex + 1];
    if (!nextSeat) {
      return;
    }
    const pending = sequence.some((step) => step.seatId === nextSeat.seatId && !stepActions[step.id]);
    if (pending) {
      return;
    }
    sequence.push({ id: createId(), seatId: nextSeat.seatId });
  }
};

const truncateSequenceAfter = (sequence: StreetActionStep[] | undefined, index: number, stepActions: Record<string, SeatAction>) => {
  if (!sequence || index < 0 || index >= sequence.length) {
    return;
  }
  const removed = sequence.splice(index + 1);
  removed.forEach((step) => {
    delete stepActions[step.id];
  });
};

const isSequenceComplete = (sequence: StreetActionStep[] | undefined, stepActions: Record<string, SeatAction>): boolean => {
  if (!sequence || sequence.length === 0) {
    return false;
  }
  return sequence.every((step) => Boolean(stepActions[step.id]));
};

const computeCompletionMap = (sequences: Record<Street, StreetActionStep[]>, stepActions: Record<string, SeatAction>): Record<Street, boolean> => {
  const map = {} as Record<Street, boolean>;
  STREET_ORDER.forEach((street) => {
    map[street] = isSequenceComplete(sequences[street], stepActions);
  });
  return map;
};

const pruneFutureStreetsAfterIncomplete = (
  sequences: Record<Street, StreetActionStep[]>,
  stepActions: Record<string, SeatAction>,
): Record<Street, boolean> => {
  const completionMap = computeCompletionMap(sequences, stepActions);
  let prune = false;
  STREET_ORDER.forEach((street) => {
    if (prune) {
      const sequence = sequences[street] ?? [];
      sequence.forEach((step) => delete stepActions[step.id]);
      sequences[street] = [];
      completionMap[street] = false;
    }
    if (!completionMap[street]) {
      prune = true;
    }
  });
  return completionMap;
};

const takeSnapshot = (state: TableComposerState): TableComposerSnapshot => ({
  seats: cloneSeats(state.seats),
  buttonSeatId: state.buttonSeatId,
  focalSeatId: state.focalSeatId,
  focalStreet: state.focalStreet,
  flopTextureKeys: [...state.flopTextureKeys],
  excludeHero: state.excludeHero,
  tableSize: state.tableSize,
  streetSequences: cloneSequences(state.streetSequences),
  stepActions: cloneStepActions(state.stepActions),
  nextStepId: state.nextStepId,
});

const restoreSnapshot = (snapshot: TableComposerSnapshot, history: TableComposerSnapshot[], future: TableComposerSnapshot[]): TableComposerState => ({
  seats: cloneSeats(snapshot.seats),
  buttonSeatId: snapshot.buttonSeatId,
  focalSeatId: snapshot.focalSeatId,
  focalStreet: snapshot.focalStreet,
  flopTextureKeys: [...snapshot.flopTextureKeys],
  excludeHero: snapshot.excludeHero,
  tableSize: snapshot.tableSize,
  streetSequences: cloneSequences(snapshot.streetSequences),
  stepActions: cloneStepActions(snapshot.stepActions),
  nextStepId: snapshot.nextStepId,
  history,
  future,
});

export const createInitialTableComposerState = (preset: TableComposerPreset = DEFAULT_PRESET): TableComposerState => {
  const size = clampTableSize(DEFAULT_TABLE_SIZE);
  const seats = applyTableSize(cloneSeats(preset.seats), size);
  let nextStepId = 1;
  const sequences = buildInitialSequences(seats, () => createStepId(nextStepId++));
  const focalSeatId = determineInitialFocalSeat(seats);
  let buttonSeatId = preset.buttonSeatId;
  if (!seats.some((seat) => seat.seatId === buttonSeatId && seat.isActive)) {
    buttonSeatId = determineInitialFocalSeat(seats);
  }
  return {
    seats,
    buttonSeatId,
    focalSeatId,
    focalStreet: 'flop',
    flopTextureKeys: [],
    excludeHero: true,
    tableSize: size,
    history: [],
    future: [],
    streetSequences: sequences,
    stepActions: {},
    nextStepId,
  };
};

const pushHistory = (state: TableComposerState): TableComposerState => ({
  ...state,
  history: [...state.history, takeSnapshot(state)],
  future: [],
});

export const tableComposerReducer: Reducer<TableComposerState, TableComposerAction> = (state, action) => {
  switch (action.type) {
    case 'toggle_seat_active': {
      const next = pushHistory(state);
      const toggledSeats = next.seats.map((seat) => {
        if (seat.seatId !== action.seatId) {
          return seat;
        }
        const isActive = !seat.isActive;
        return {
          ...seat,
          isActive,
          actions: isActive ? seat.actions : {},
        };
      });
      const size = clampTableSize(activeSeatCount(toggledSeats));
      const normalizedSeats = applyTableSize(toggledSeats, size);
      let focalSeatId = next.focalSeatId;
      if (!normalizedSeats.some((seat) => seat.seatId === focalSeatId && seat.isActive)) {
        focalSeatId = determineInitialFocalSeat(normalizedSeats);
      }
      let buttonSeatId = next.buttonSeatId;
      if (!normalizedSeats.some((seat) => seat.seatId === buttonSeatId && seat.isActive)) {
        buttonSeatId = determineInitialFocalSeat(normalizedSeats);
      }
      let nextStepId = next.nextStepId;
      const { sequences: prunedSequences, stepActions: prunedActions } = pruneSequencesForActiveSeats(
        next.streetSequences,
        next.stepActions,
        normalizedSeats,
      );
      ensurePreflopCoverage(prunedSequences, normalizedSeats, prunedActions, () => createStepId(nextStepId++));
      const completionMap = pruneFutureStreetsAfterIncomplete(prunedSequences, prunedActions);
      ensurePostFlopEligibility(prunedSequences, normalizedSeats, prunedActions, () => createStepId(nextStepId++), completionMap);
      STREET_ORDER.forEach((street) => {
        ensureContinuationSteps(street, prunedSequences, prunedActions, normalizedSeats, () => createStepId(nextStepId++));
      });
      const syncedSeats = syncSeatActionsWithSteps(normalizedSeats, prunedSequences, prunedActions);
      return {
        ...next,
        seats: syncedSeats,
        tableSize: size,
        focalSeatId,
        buttonSeatId,
        streetSequences: prunedSequences,
        stepActions: prunedActions,
        nextStepId,
      };
    }
    case 'set_button': {
      const next = pushHistory(state);
      return {
        ...next,
        buttonSeatId: action.seatId,
      };
    }
    case 'set_action': {
      const next = pushHistory(state);
      return {
        ...next,
        seats: next.seats.map((seat) =>
          seat.seatId === action.seatId
            ? {
                ...seat,
                actions:
                  action.action === null
                    ? Object.fromEntries(
                        Object.entries(seat.actions).filter(([street]) => street !== action.street),
                      )
                    : { ...seat.actions, [action.street]: action.action },
              }
            : seat,
        ),
      };
    }
    case 'set_seat_actions': {
      const next = pushHistory(state);
      return {
        ...next,
        seats: next.seats.map((seat) =>
          seat.seatId === action.seatId
            ? {
                ...seat,
                actions: STREET_ORDER.reduce<Partial<Record<Street, SeatAction>>>((acc, street) => {
                  const value = action.actions[street];
                  if (value) {
                    acc[street] = value;
                  }
                  return acc;
                }, {}),
              }
            : seat,
        ),
      };
    }
    case 'set_focal': {
      return {
        ...state,
        focalSeatId: action.seatId,
        focalStreet: action.street ?? state.focalStreet,
      };
    }
    case 'set_flop_textures': {
      const next = pushHistory(state);
      return {
        ...next,
        flopTextureKeys: [...action.keys],
      };
    }
    case 'set_exclude_hero': {
      return {
        ...state,
        excludeHero: action.exclude,
      };
    }
    case 'set_table_size': {
      const size = clampTableSize(action.size);
      const next = pushHistory(state);
      const updatedSeats = applyTableSize(next.seats, size);
      let focalSeatId = next.focalSeatId;
      if (!updatedSeats.some((seat) => seat.seatId === focalSeatId && seat.isActive)) {
        focalSeatId = determineInitialFocalSeat(updatedSeats);
      }
      let buttonSeatId = next.buttonSeatId;
      if (!updatedSeats.some((seat) => seat.seatId === buttonSeatId && seat.isActive)) {
        buttonSeatId = determineInitialFocalSeat(updatedSeats);
      }
      let nextStepId = next.nextStepId;
      const { sequences: prunedSequences, stepActions: prunedActions } = pruneSequencesForActiveSeats(
        next.streetSequences,
        next.stepActions,
        updatedSeats,
      );
      ensurePreflopCoverage(prunedSequences, updatedSeats, prunedActions, () => createStepId(nextStepId++));
      const completionMap = pruneFutureStreetsAfterIncomplete(prunedSequences, prunedActions);
      ensurePostFlopEligibility(prunedSequences, updatedSeats, prunedActions, () => createStepId(nextStepId++), completionMap);
      STREET_ORDER.forEach((street) => {
        ensureContinuationSteps(street, prunedSequences, prunedActions, updatedSeats, () => createStepId(nextStepId++));
      });
      const syncedSeats = syncSeatActionsWithSteps(updatedSeats, prunedSequences, prunedActions);
      return {
        ...next,
        seats: syncedSeats,
        tableSize: size,
        focalSeatId,
        buttonSeatId,
        streetSequences: prunedSequences,
        stepActions: prunedActions,
        nextStepId,
      };
    }
    case 'apply_actions': {
      if (!action.items.length) {
        return state;
      }
      const next = pushHistory(state);
      const updatedSequences = cloneSequences(next.streetSequences);
      const updatedActions = cloneStepActions(next.stepActions);
      let nextStepId = next.nextStepId;
      const touchedStreets = new Set<Street>();

      const anchor = action.items[action.items.length - 1];
      action.items.forEach((item) => {
        let sequence = updatedSequences[item.street];
        if (!sequence) {
          sequence = [];
          updatedSequences[item.street] = sequence;
        }
        let targetIndex = -1;
        for (let index = sequence.length - 1; index >= 0; index -= 1) {
          if (sequence[index].seatId === item.seatId) {
            targetIndex = index;
            break;
          }
        }
        if (targetIndex === -1) {
          sequence.push({
            id: createStepId(nextStepId++),
            seatId: item.seatId,
          });
          targetIndex = sequence.length - 1;
        }
        const target = sequence[targetIndex];
        if (item.action === null) {
          delete updatedActions[target.id];
        } else {
          updatedActions[target.id] = cloneSeatAction(item.action);
          ensurePriorStepsFilled(sequence, targetIndex, updatedActions);
        }
        if (item === anchor) {
          truncateSequenceAfter(sequence, targetIndex, updatedActions);
        }
        touchedStreets.add(item.street);
      });

      touchedStreets.forEach((street) => {
        if (street === 'preflop') {
          ensurePreflopCoverage(updatedSequences, next.seats, updatedActions, () => createStepId(nextStepId++));
        }
      });
      const completionMap = pruneFutureStreetsAfterIncomplete(updatedSequences, updatedActions);
      ensurePostFlopEligibility(updatedSequences, next.seats, updatedActions, () => createStepId(nextStepId++), completionMap);
      touchedStreets.forEach((street) => {
        ensureContinuationSteps(street, updatedSequences, updatedActions, next.seats, () => createStepId(nextStepId++));
      });
      pruneFutureStreetsAfterIncomplete(updatedSequences, updatedActions);

      const syncedSeats = syncSeatActionsWithSteps(next.seats, updatedSequences, updatedActions);
      return {
        ...next,
        seats: syncedSeats,
        streetSequences: updatedSequences,
        stepActions: updatedActions,
        nextStepId,
      };
    }
    case 'apply_step_changes': {
      const updates = action.updates ?? [];
      const append = action.append ?? [];
      const remove = action.remove ?? [];
      if (updates.length === 0 && append.length === 0 && remove.length === 0) {
        return state;
      }
      const next = pushHistory(state);
      const updatedSequences = cloneSequences(next.streetSequences);
      const updatedActions = cloneStepActions(next.stepActions);
      let nextStepId = next.nextStepId;

      if (remove.length > 0) {
        const removeSet = new Set(remove);
        STREET_ORDER.forEach((street) => {
          updatedSequences[street] = updatedSequences[street].filter((step) => {
            if (removeSet.has(step.id)) {
              delete updatedActions[step.id];
              return false;
            }
            return true;
          });
        });
      }

      let sequence = updatedSequences[action.street];
      if (!sequence) {
        sequence = [];
        updatedSequences[action.street] = sequence;
      }

      let truncateIndex = -1;
      updates.forEach((update) => {
        const index = sequence.findIndex((step) => step.id === update.stepId);
        if (index > truncateIndex) {
          truncateIndex = index;
        }
      });
      if (truncateIndex !== -1) {
        truncateSequenceAfter(sequence, truncateIndex, updatedActions);
      }

      if (append.length > 0) {
        append.forEach(({ seatId, afterStepId }) => {
          const targetStreet = action.street;
          let targetSequence = updatedSequences[targetStreet];
          if (!targetSequence) {
            targetSequence = [];
            updatedSequences[targetStreet] = targetSequence;
          }
          const newStep: StreetActionStep = {
            id: createStepId(nextStepId++),
            seatId,
          };
          const afterIndex = afterStepId ? targetSequence.findIndex((step) => step.id === afterStepId) : -1;
          const insertAt = afterStepId && afterIndex !== -1 ? afterIndex + 1 : targetSequence.length;
          targetSequence.splice(insertAt, 0, newStep);
        });
      }

      if (updates.length > 0) {
        updates.forEach((update) => {
          if (update.action === null) {
            delete updatedActions[update.stepId];
          } else {
            updatedActions[update.stepId] = cloneSeatAction(update.action);
            const seq = updatedSequences[action.street] ?? [];
            const idx = seq.findIndex((step) => step.id === update.stepId);
            if (idx > 0) {
              ensurePriorStepsFilled(seq, idx, updatedActions);
            }
          }
        });
      }

      if (action.street === 'preflop') {
        ensurePreflopCoverage(updatedSequences, next.seats, updatedActions, () => createStepId(nextStepId++));
      }

      const completionMap = pruneFutureStreetsAfterIncomplete(updatedSequences, updatedActions);
      ensurePostFlopEligibility(updatedSequences, next.seats, updatedActions, () => createStepId(nextStepId++), completionMap);
      ensureContinuationSteps(action.street, updatedSequences, updatedActions, next.seats, () => createStepId(nextStepId++));
      pruneFutureStreetsAfterIncomplete(updatedSequences, updatedActions);

      const syncedSeats = syncSeatActionsWithSteps(next.seats, updatedSequences, updatedActions);

      return {
        ...next,
        seats: syncedSeats,
        streetSequences: updatedSequences,
        stepActions: updatedActions,
        nextStepId,
      };
    }
    case 'undo': {
      if (state.history.length === 0) {
        return state;
      }
      const history = [...state.history];
      const previous = history.pop()!;
      const future = [takeSnapshot(state), ...state.future];
      return restoreSnapshot(previous, history, future);
    }
    case 'redo': {
      if (state.future.length === 0) {
        return state;
      }
      const [nextSnapshot, ...restFuture] = state.future;
      const history = [...state.history, takeSnapshot(state)];
      return restoreSnapshot(nextSnapshot, history, restFuture);
    }
    case 'reset': {
      const preset = action.preset ?? DEFAULT_PRESET;
      return createInitialTableComposerState(preset);
    }
    default:
      return state;
  }
};

/**
 * Translate the table composer state into the descriptor expected by the
 * backend. Seats are ordered clockwise starting from the button seat.
 */
export const deriveDescriptorFromTable = (state: TableComposerState) => {
  const steps: Array<{
    street: Street;
    actor: string;
    action: string;
    qualifiers?: string[];
    sizing?: { bucket_keys?: string[]; ratio_min?: number | null; ratio_max?: number | null; absolute_bb?: number | null; label?: string | null };
  }> = [];

  const activeSeats = state.seats.filter((seat) => seat.isActive);
  const focalSeat = state.focalSeatId ? activeSeats.find((seat) => seat.seatId === state.focalSeatId) : activeSeats[0];

  if (focalSeat) {
    const positionQualifier = derivePositionQualifier(focalSeat.position, activeSeats);
    const sharedFlopQualifiers = [
      ...state.flopTextureKeys.map((value) => `texture_${value}`),
      ...(activeSeats.length === 2 ? ['heads_up'] : activeSeats.length > 2 ? ['multiway'] : []),
    ];

    const flopAction = focalSeat.actions['flop'];
    const flopDescriptor = normaliseFlopAction(flopAction);
    if (flopDescriptor) {
      const qualifiers = [...sharedFlopQualifiers];
      if (positionQualifier) {
        qualifiers.push(positionQualifier);
      }
      steps.push({
        street: 'flop',
        actor: 'responder',
        action: flopDescriptor.action,
        qualifiers,
      });
    }

    const turnAction = focalSeat.actions['turn'];
    const turnDescriptor = normaliseTurnAction(turnAction);
    if (turnDescriptor) {
      const qualifiers: string[] = [];
      if (positionQualifier) {
        qualifiers.push(positionQualifier);
      }
      steps.push({
        street: 'turn',
        actor: 'bettor',
        action: turnDescriptor.action,
        qualifiers,
        sizing: turnDescriptor.sizing,
      });
    }
  }

  return {
    steps,
    focus: 'response',
    filters: {
      excludeHero: state.excludeHero,
    },
  };
};

const FLOP_POSITION_ORDER: SeatPosition[] = ['SB', 'BB', 'UTG', 'UTG+1', 'UTG+2', 'UTG+3', 'LJ', 'HJ', 'CO', 'BTN'];

const derivePositionQualifier = (position: SeatPosition, activeSeats: SeatState[]): string | null => {
  const activePositions = FLOP_POSITION_ORDER.filter((entry) => activeSeats.some((seat) => seat.position === entry));
  if (activePositions.length < 2) {
    return null;
  }
  const focalIndex = activePositions.indexOf(position);
  if (focalIndex === -1) {
    return null;
  }
  return focalIndex === activePositions.length - 1 ? 'in_position' : 'out_of_position';
};

const normaliseFlopAction = (action?: SeatAction) => {
  if (!action) {
    return null;
  }
  if (action.action === 'call') {
    return { action: 'call' };
  }
  if (action.action === 'raise') {
    return { action: 'raise' };
  }
  if (action.action === 'bet') {
    return { action: 'raise' };
  }
  if (action.action === 'check' || action.action === 'limp') {
    return { action: 'check' };
  }
  if (action.action === 'fold') {
    return { action: 'fold' };
  }
  return null;
};

const normaliseTurnAction = (action?: SeatAction) => {
  if (!action) {
    return null;
  }
  if (action.action === 'bet' || action.action === 'raise') {
    return {
      action: action.action,
      sizing: convertSizing(action.sizing),
    };
  }
  if (action.action === 'check') {
    return { action: 'check' };
  }
  if (action.action === 'call') {
    return { action: 'call' };
  }
  if (action.action === 'fold') {
    return { action: 'fold' };
  }
  return null;
};

const convertSizing = (
  sizing: ActionSizing | undefined,
): { bucket_keys?: string[]; ratio_min?: number | null; ratio_max?: number | null; absolute_bb?: number | null; label?: string | null } | undefined => {
  if (!sizing) {
    return undefined;
  }
  switch (sizing.kind) {
    case 'pot_ratio':
      return {
        ratio_min: sizing.value,
        ratio_max: sizing.value,
      };
    case 'bb_multiple':
      return {
        label: `${sizing.value}x`,
      };
    case 'label':
      return {
        label: sizing.value,
      };
    case 'bucket':
      return {
        bucket_keys: [sizing.key],
      };
    default:
      return undefined;
  }
};

const computeSeatOrder = (state: TableComposerState): SeatState[] => {
  const seats = state.seats.filter((seat) => seat.isActive);
  if (seats.length === 0) {
    return [];
  }
  if (!state.buttonSeatId) {
    return seats;
  }
  const buttonIndex = seats.findIndex((seat) => seat.seatId === state.buttonSeatId);
  if (buttonIndex === -1) {
    return seats;
  }
  return [...seats.slice(buttonIndex), ...seats.slice(0, buttonIndex)];
};

const activeSeatCount = (seats: SeatState[]) => seats.filter((seat) => seat.isActive).length;

const clampTableSize = (size: number): number => Math.max(MIN_TABLE_SIZE, Math.min(MAX_TABLE_SIZE, Math.floor(size)));

const applyTableSize = (seats: SeatState[], size: number): SeatState[] => {
  const activePositions = new Set(deriveActivePositions(size));
  return seats.map((seat) => {
    const isActive = activePositions.has(seat.position);
    return {
      ...seat,
      isActive,
      actions: isActive ? seat.actions : {},
    };
  });
};

const determineInitialFocalSeat = (seats: SeatState[]): string | null => {
  const seat = seats.find((entry) => entry.isActive);
  return seat ? seat.seatId : null;
};

const deriveActivePositions = (size: number): SeatPosition[] => {
  const target = clampTableSize(size);
  const positions = [...DEFAULT_SEAT_ORDER];
  const removeCount = Math.max(0, positions.length - target);
  for (let index = 0; index < removeCount && index < REMOVAL_PRIORITY.length; index += 1) {
    const toRemove = REMOVAL_PRIORITY[index];
    const removeIndex = positions.indexOf(toRemove);
    if (removeIndex >= 0) {
      positions.splice(removeIndex, 1);
    }
  }
  return positions;
};
