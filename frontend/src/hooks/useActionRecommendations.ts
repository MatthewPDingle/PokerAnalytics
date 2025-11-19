import { useEffect, useMemo, useState } from 'react';

export type ActionRecommendationRow = {
  street: 'Flop' | 'Turn' | 'River';
  preflopAction: string;
  betClassification: string;
  flopTexture: string;
  players: string;
  bettorPosition: string;
  sprBucket: string;
  situation: 'Bluff' | 'Value';
  action: string;
  rank: number;
  // Parsed metrics used for sorting/filtering
  sampleSize: number;
  foldSurplus: number | null;
  potShareAdded: number | null;
  // Parsed breakdown for table display
  bucketLabel: string;
  foldPct: number | null;
  callPct: number | null;
  raisePct: number | null;
  breakevenFoldPct: number | null;
  avgBetPct: number | null;
};

type RawRow = {
  street: 'Flop' | 'Turn' | 'River';
  preflop_action: string;
  bet_classification: string;
  flop_texture: string;
  players: string;
  bettor_position: string;
  spr_bucket: string;
  situation: 'Bluff' | 'Value';
  action: string;
  rank: number;
  avg_bet_pct?: number;
};

type RawPayload = {
  version: number;
  rows: RawRow[];
};

type HookState = {
  rows: ActionRecommendationRow[];
  loading: boolean;
  error: string | null;
  usingSample: boolean;
};

const parseSampleSize = (text: string): number => {
  const match = text.match(/n=(\d+)/);
  if (!match) {
    return 0;
  }
  return Number.parseInt(match[1], 10) || 0;
};

const parseFoldSurplus = (text: string): number | null => {
  const match = text.match(/fold surplus ([+-]?[0-9.]+)pp/);
  if (!match) {
    return null;
  }
  const value = Number.parseFloat(match[1]);
  return Number.isFinite(value) ? value : null;
};

const parsePotShareAdded = (text: string): number | null => {
  const match = text.match(/adds ([0-9.]+)[×x] pot/);
  if (!match) {
    return null;
  }
  const value = Number.parseFloat(match[1]);
  return Number.isFinite(value) ? value : null;
};

const parseBucketLabel = (text: string): string => {
  const match = text.match(/^Bet (.+?) —/);
  if (!match) {
    return '';
  }
  return match[1];
};

const parseFoldCallRaise = (
  text: string,
): { foldPct: number | null; callPct: number | null; raisePct: number | null } => {
  const foldMatch = text.match(/folds ([0-9.]+)%/);
  const callMatch = text.match(/calls ([0-9.]+)%/);
  const raiseMatch = text.match(/raises ([0-9.]+)%/);

  const call = callMatch ? Number.parseFloat(callMatch[1]) : null;
  const raise = raiseMatch ? Number.parseFloat(raiseMatch[1]) : null;
  let fold = foldMatch ? Number.parseFloat(foldMatch[1]) : null;

  if (!Number.isFinite(call ?? NaN) || !Number.isFinite(raise ?? NaN)) {
    return {
      foldPct: Number.isFinite(fold ?? NaN) ? (fold as number) : null,
      callPct: Number.isFinite(call ?? NaN) ? (call as number) : null,
      raisePct: Number.isFinite(raise ?? NaN) ? (raise as number) : null,
    };
  }

  if (!Number.isFinite(fold ?? NaN)) {
    const total = (call as number) + (raise as number);
    if (Number.isFinite(total) && total <= 100) {
      fold = Math.max(0, 100 - total);
    } else {
      fold = null;
    }
  }

  return {
    foldPct: Number.isFinite(fold ?? NaN) ? (fold as number) : null,
    callPct: Number.isFinite(call ?? NaN) ? (call as number) : null,
    raisePct: Number.isFinite(raise ?? NaN) ? (raise as number) : null,
  };
};

const parseBreakevenFoldPct = (
  text: string,
  foldPct: number | null,
  foldSurplus: number | null,
): number | null => {
  const match = text.match(/vs ([0-9.]+)% breakeven/);
  if (match) {
    const value = Number.parseFloat(match[1]);
    return Number.isFinite(value) ? value : null;
  }
  if (foldPct != null && foldSurplus != null) {
    const value = foldPct - foldSurplus;
    return Number.isFinite(value) ? value : null;
  }
  return null;
};

const transformPayload = (payload: RawPayload): HookState => {
  const rows: ActionRecommendationRow[] = payload.rows.map((row) => {
    const sampleSize = parseSampleSize(row.action);
    const foldSurplus = parseFoldSurplus(row.action);
    const potShareAdded = parsePotShareAdded(row.action);
    const bucketLabel = parseBucketLabel(row.action);
    const { foldPct, callPct, raisePct } = parseFoldCallRaise(row.action);
    const breakevenFoldPct = parseBreakevenFoldPct(row.action, foldPct, foldSurplus);

    return {
      street: row.street,
      preflopAction: row.preflop_action,
      betClassification: row.bet_classification,
      flopTexture: row.flop_texture,
      players: row.players,
      bettorPosition: row.bettor_position,
      sprBucket: row.spr_bucket,
      situation: row.situation,
      action: row.action,
      rank: row.rank,
      sampleSize,
      foldSurplus,
      potShareAdded,
      bucketLabel,
      foldPct,
      callPct,
      raisePct,
      breakevenFoldPct,
      avgBetPct:
        typeof row.avg_bet_pct === 'number' && Number.isFinite(row.avg_bet_pct)
          ? row.avg_bet_pct
          : null,
    };
  });

  return {
    rows,
    loading: false,
    error: null,
    usingSample: false,
  };
};

const SAMPLE_STATE: HookState = {
  rows: [],
  loading: false,
  error: 'Action recommendations are unavailable (API error).',
  usingSample: true,
};

export const useActionRecommendations = (sourceKey: string | null) => {
  const [state, setState] = useState<HookState>({
    rows: [],
    loading: true,
    error: null,
    usingSample: false,
  });

  useEffect(() => {
    let active = true;

    setState((prev) => ({
      ...prev,
      loading: true,
      error: null,
      usingSample: false,
    }));

    const fetchData = async () => {
      try {
        const url =
          sourceKey && sourceKey.trim().length > 0
            ? `/api/action-reference?source=${encodeURIComponent(sourceKey)}`
            : '/api/action-reference';
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }
        const payload = (await response.json()) as RawPayload;
        if (!active) {
          return;
        }
        setState(transformPayload(payload));
      } catch (err) {
        if (!active) {
          return;
        }
        setState(SAMPLE_STATE);
      }
    };

    fetchData();

    return () => {
      active = false;
    };
  }, [sourceKey]);

  return useMemo(() => state, [state]);
};
