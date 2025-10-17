export const POSITION_PRIORITY: Record<string, number> = {
  SB: 0,
  BB: 1,
  LJ: 2,
  HJ: 3,
  CO: 4,
  BTN: 5,
  UTG: 6,
  'UTG+1': 7,
  'UTG+2': 8,
  MP: 9,
  UNKNOWN: 10,
};

export const sortPositions = <T extends { position: string }>(list: T[]): T[] =>
  [...list].sort((a, b) => {
    const aPriority = POSITION_PRIORITY[a.position] ?? Number.MAX_SAFE_INTEGER;
    const bPriority = POSITION_PRIORITY[b.position] ?? Number.MAX_SAFE_INTEGER;
    return aPriority - bPriority || a.position.localeCompare(b.position);
  });
