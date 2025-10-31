export const FLOP_TEXTURE_DEFINITIONS: Record<string, string> = {
  Rainbow: 'All suits represented with no repeats.',
  Monotone: 'Every card shares the same suit.',
  'Two Tone': 'Board uses exactly two suits.',
  Paired: 'Some rank appears at least twice.',
  'Connected (≤4 Gap)': 'Highest and lowest ranks within four, wheel-aware.',
  'Ace High': 'Ace present and is the highest rank.',
  'Low (≤ Ten)': 'All ranks Ten or lower.',
  'High Broadway': 'At least two cards Jack or higher.',
};

export const TURN_RIVER_TEXTURE_DEFINITIONS: Record<string, string> = {
  '3 Suited Cards': 'Three cards share a suit.',
  '4 Suited Cards': 'Four cards share a suit.',
  '5 Suited Cards': 'Five cards share a suit.',
  '3 Connected Ranks': 'Three sequential ranks without gaps.',
  '4 Connected Ranks': 'Four sequential ranks without gaps.',
  '5 Connected Ranks': 'Five sequential ranks without gaps.',
  Trips: 'Some rank appears exactly three times.',
  Quads: 'Some rank appears four times.',
};
