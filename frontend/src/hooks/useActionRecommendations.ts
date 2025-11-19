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

const transformPayload = (payload: RawPayload): HookState => {
  const rows: ActionRecommendationRow[] = payload.rows.map((row) => {
    const sampleSize = parseSampleSize(row.action);
    const foldSurplus = parseFoldSurplus(row.action);
    const potShareAdded = parsePotShareAdded(row.action);

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
