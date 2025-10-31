import { describe, expect, it } from 'vitest';

import {
  createInitialTableComposerState,
  tableComposerReducer,
  TableComposerState,
  SeatAction,
  Street,
} from './tableComposer';

const getNextStepId = (state: TableComposerState, street: Street, seatId: string): string => {
  const sequence = state.streetSequences[street] ?? [];
  for (const step of sequence) {
    if (step.seatId !== seatId) {
      continue;
    }
    if (!state.stepActions[step.id]) {
      return step.id;
    }
  }
  const fallback = sequence.find((step) => step.seatId === seatId);
  if (!fallback) {
    throw new Error(`No step available for ${seatId} on ${street}`);
  }
  return fallback.id;
};

const applySeatAction = (
  state: TableComposerState,
  seatId: string,
  street: Street,
  action: SeatAction,
): TableComposerState => {
  const stepId = getNextStepId(state, street, seatId);
  return tableComposerReducer(state, {
    type: 'apply_step_changes',
    street,
    updates: [{ stepId, action }],
  });
};

describe('tableComposer sequencing', () => {
  it('assigns default stacks of 100 BB to each seat', () => {
    const state = createInitialTableComposerState();
    state.seats.forEach((seat) => {
      expect(seat.startingStack).toBe(100);
    });
  });

  it('retains preflop placeholders after first action', () => {
    let state = createInitialTableComposerState();
    const initialSeatIds = state.streetSequences.preflop.map((step) => step.seatId);

    state = applySeatAction(state, 'seat-UTG', 'preflop', { action: 'limp' });

    expect(state.streetSequences.preflop.map((step) => step.seatId)).toEqual(initialSeatIds);
  });

  it('populates flop placeholders after preflop closes with limp and check', () => {
    let state = createInitialTableComposerState();

    const sequenceOrder = state.streetSequences.preflop.map((step) => step.seatId);
    const actionPlan: Record<string, SeatAction> = {
      'seat-UTG': { action: 'limp' },
      'seat-UTG+1': { action: 'fold' },
      'seat-UTG+2': { action: 'fold' },
      'seat-UTG+3': { action: 'fold' },
      'seat-SB': { action: 'fold' },
      'seat-BB': { action: 'check' },
    };

    sequenceOrder.forEach((seatId) => {
      const plannedAction = actionPlan[seatId] ?? { action: 'fold' };
      state = applySeatAction(state, seatId, 'preflop', plannedAction);
    });

    expect(state.streetSequences.flop.map((step) => step.seatId)).toEqual(['seat-BB', 'seat-UTG']);
    expect(state.streetSequences.turn.length).toBe(0);
  });

  it('creates river placeholders after turn checks', () => {
    let state = createInitialTableComposerState();
    const preflopPlan: Record<string, SeatAction> = {
      'seat-UTG': { action: 'limp' },
      'seat-UTG+1': { action: 'fold' },
      'seat-UTG+2': { action: 'fold' },
      'seat-UTG+3': { action: 'fold' },
      'seat-SB': { action: 'fold' },
      'seat-BB': { action: 'check' },
    };
    const preflopOrder = state.streetSequences.preflop.map((step) => step.seatId);
    preflopOrder.forEach((seatId) => {
      const planned = preflopPlan[seatId] ?? { action: 'fold' };
      state = applySeatAction(state, seatId, 'preflop', planned);
    });

    const flopOrder = state.streetSequences.flop.map((step) => step.seatId);
    flopOrder.forEach((seatId) => {
      state = applySeatAction(state, seatId, 'flop', { action: 'check' });
    });

    expect(state.streetSequences.turn.map((step) => step.seatId)).toEqual(['seat-BB', 'seat-UTG']);

    const turnOrder = state.streetSequences.turn.map((step) => step.seatId);
    turnOrder.forEach((seatId) => {
      state = applySeatAction(state, seatId, 'turn', { action: 'check' });
    });

    expect(state.streetSequences.river.map((step) => step.seatId)).toEqual(['seat-BB', 'seat-UTG']);
  });
});
