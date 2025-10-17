import { Table, Tbody, Td, Th, Thead, Tr } from '@chakra-ui/react';

type ValueGridProps = {
  rows: string[];
  cols: string[];
  values: number[][];
  format?: (value: number) => string;
};

type Rgb = [number, number, number];

type ColorResult = {
  background: string;
  textColor: string;
};

const RED: Rgb = [185, 28, 28];
const WHITE: Rgb = [255, 255, 255];
const GREEN: Rgb = [22, 163, 74];

const EPSILON = 1e-6;

const clampRatio = (value: number) => Math.min(1, Math.max(0, value));
const clampChannel = (value: number) => Math.min(255, Math.max(0, value));
const roundToSingleDecimal = (value: number) => Math.round(value * 10) / 10;

const mix = (start: Rgb, end: Rgb, ratio: number): Rgb => [
  start[0] + (end[0] - start[0]) * ratio,
  start[1] + (end[1] - start[1]) * ratio,
  start[2] + (end[2] - start[2]) * ratio,
];

const toColorResult = (channels: Rgb): ColorResult => {
  const normalized: Rgb = [
    clampChannel(Math.round(channels[0])),
    clampChannel(Math.round(channels[1])),
    clampChannel(Math.round(channels[2])),
  ];
  const [r, g, b] = normalized;
  const brightness = 0.299 * r + 0.587 * g + 0.114 * b;
  return {
    background: `rgb(${normalized.join(', ')})`,
    textColor: brightness > 150 ? '#000' : '#fff',
  };
};

const anchoredGradient = (value: number, min: number, max: number, anchor: number): ColorResult => {
  if (!Number.isFinite(value)) {
    return toColorResult(WHITE);
  }

  if (max - min < EPSILON) {
    return toColorResult(mix(RED, GREEN, 0.5) as Rgb);
  }

  if (anchor <= min || anchor >= max) {
    const ratio = clampRatio((value - min) / (max - min));
    return toColorResult(mix(RED, GREEN, ratio) as Rgb);
  }

  if (value <= anchor) {
    const denominator = anchor - min;
    const ratio = denominator > EPSILON ? clampRatio((value - min) / denominator) : 0;
    return toColorResult(mix(RED, WHITE, ratio) as Rgb);
  }

  const denominator = max - anchor;
  const ratio = denominator > EPSILON ? clampRatio((value - anchor) / denominator) : 0;
  return toColorResult(mix(WHITE, GREEN, ratio) as Rgb);
};

const calculateBounds = (matrix: number[][]) => {
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;

  matrix.forEach((row) => {
    row.forEach((raw) => {
      const numeric = Number(raw);
      if (Number.isFinite(numeric)) {
        if (numeric < min) {
          min = numeric;
        }
        if (numeric > max) {
          max = numeric;
        }
      }
    });
  });

  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return { min: 0, max: 0 };
  }

  return { min, max };
};

const defaultFormat = (value: number): string => {
  if (!Number.isFinite(value)) {
    return '-';
  }

  if (Math.abs(value) < EPSILON) {
    return '0';
  }

  if (Number.isInteger(value)) {
    return String(value);
  }

  return value.toFixed(1);
};

const HEADER_CELL_PROPS = {
  w: '30px',
  h: '30px',
  minW: '30px',
  maxW: '30px',
  minH: '30px',
  maxH: '30px',
  p: 0,
  fontSize: '10px',
  textAlign: 'center' as const,
  verticalAlign: 'middle' as const,
  lineHeight: 'short',
  overflow: 'hidden',
  whiteSpace: 'nowrap' as const,
  textOverflow: 'clip' as const,
};

const CELL_PROPS = {
  w: '30px',
  h: '30px',
  minW: '30px',
  maxW: '30px',
  minH: '30px',
  maxH: '30px',
  p: 0,
  fontSize: '11px',
  textAlign: 'center' as const,
  verticalAlign: 'middle' as const,
  lineHeight: 'short',
  overflow: 'hidden',
  whiteSpace: 'nowrap' as const,
  textOverflow: 'clip' as const,
};

const ValueGrid = ({ rows, cols, values, format }: ValueGridProps) => {
  const { min, max } = calculateBounds(values);

  const tableWidth = (cols.length + 1) * 30;
  const tableHeight = (rows.length + 1) * 30;

  return (
    <Table
      size="sm"
      variant="unstyled"
      w={`${tableWidth}px`}
      h={`${tableHeight}px`}
      sx={{
        tableLayout: 'fixed',
        borderCollapse: 'separate',
        borderSpacing: '0',
      }}
    >
      <Thead>
        <Tr>
          <Th bg="blackAlpha.500" position="sticky" top={0} zIndex={1} color="white" {...HEADER_CELL_PROPS} />
          {cols.map((col) => (
            <Th key={col} bg="blackAlpha.500" color="white" {...HEADER_CELL_PROPS}>
              {col}
            </Th>
          ))}
        </Tr>
      </Thead>
      <Tbody>
        {rows.map((row, i) => (
          <Tr key={row}>
            <Th bg="blackAlpha.500" position="sticky" left={0} zIndex={1} color="white" {...HEADER_CELL_PROPS}>
              {row}
            </Th>
            {cols.map((col, j) => {
              const value = Number(values[i]?.[j] ?? 0);
              const { background, textColor } = anchoredGradient(value, min, max, 0);
              const roundedForDisplay = roundToSingleDecimal(value);
              const displayValue = Number.isFinite(value)
                ? format
                  ? format(roundedForDisplay)
                  : defaultFormat(roundedForDisplay)
                : '-';

              return (
                <Td key={`${row}-${col}`} bg={background} color={textColor} {...CELL_PROPS}>
                  {displayValue}
                </Td>
              );
            })}
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
};

export default ValueGrid;
