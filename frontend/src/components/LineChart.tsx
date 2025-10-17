import { Box } from '@chakra-ui/react';
import { useEffect, useMemo, useRef, useState } from 'react';

export type LineChartPoint = {
  x: number;
  y: number;
  label?: string;
};

export type LineChartProps = {
  points: LineChartPoint[];
  height?: number;
  stroke?: string;
  strokeWidth?: number;
  showZeroLine?: boolean;
  xLabel?: string;
  yLabel?: string;
  xTickMinStep?: number;
  yTickMinStep?: number;
  highlighted?: boolean;
};

const BASE_WIDTH = 800;
const AXIS_FONT = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif";
const PADDING = {
  top: 40,
  right: 32,
  bottom: 64,
  left: 88,
};

const niceStep = (range: number, maxTicks: number, minStep: number) => {
  if (range <= 0) {
    return minStep;
  }
  const rough = range / Math.max(1, maxTicks);
  const exponent = Math.floor(Math.log10(rough));
  const magnitude = Math.pow(10, exponent);
  const candidates = [1, 2, 4, 5, 10];
  const scaled = candidates.map((c) => c * magnitude);
  const chosen = scaled.reduce((prev, curr) => (Math.abs(curr - rough) < Math.abs(prev - rough) ? curr : prev));
  return Math.max(chosen, minStep);
};

const buildTicks = (min: number, max: number, maxTicks: number, minStep: number) => {
  const range = max - min;
  const step = niceStep(range, maxTicks, minStep);
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let value = start; value <= max; value += step) {
    ticks.push(Number(value.toFixed(6)));
  }
  return ticks;
};

const LineChart = ({
  points,
  height = 320,
  stroke = '#63b3ed',
  strokeWidth = 2,
  showZeroLine = true,
  xLabel = 'Hand Index',
  yLabel = 'Cumulative Net (bb)',
  xTickMinStep = 200,
  yTickMinStep = 100,
  highlighted = false,
}: LineChartProps) => {
  const padding = PADDING;
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [containerWidth, setContainerWidth] = useState(BASE_WIDTH);

  useEffect(() => {
    const node = svgRef.current;
    if (!node) {
      return;
    }
    const initialWidth = node.getBoundingClientRect().width;
    if (initialWidth > 0) {
      setContainerWidth(initialWidth);
    }
    if (typeof ResizeObserver === 'undefined') {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const nextWidth = entry.contentRect.width;
        if (nextWidth > 0) {
          setContainerWidth(nextWidth);
        }
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const chartWidth = Math.max(containerWidth, padding.left + padding.right + 1);

  const plotLeft = padding.left;
  const plotRight = chartWidth - padding.right;
  const plotTop = padding.top;
  const plotBottom = height - padding.bottom;
  const innerWidth = Math.max(plotRight - plotLeft, 1);
  const innerHeight = plotBottom - plotTop;
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const [tooltip, setTooltip] = useState<
    { x: number; y: number; screenX: number; screenY: number; label?: string } | null
  >(null);

  if (points.length === 0) {
    return (
      <Box h={`${height}px`} display="flex" alignItems="center" justifyContent="center" color="whiteAlpha.600">
        No data
      </Box>
    );
  }

  const { minX, maxX, minY, maxY, xRange, yRange, projectX, projectY, xTicks, yTicks } = useMemo(() => {
    const xs = points.map((p) => p.x);
    const ys = points.map((p) => p.y);
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    const yMin = Math.min(Math.min(...ys), showZeroLine ? 0 : Math.min(...ys));
    const yMax = Math.max(Math.max(...ys), showZeroLine ? 0 : Math.max(...ys));
    const xR = xMax - xMin || 1;
    const yR = yMax - yMin || 1;
    const projectXFn = (x: number) => plotLeft + ((x - xMin) / xR) * innerWidth;
    const projectYFn = (y: number) => plotBottom - ((y - yMin) / yR) * innerHeight;
    const xt = buildTicks(xMin, xMax, 8, xTickMinStep);
    const yt = buildTicks(yMin, yMax, 7, yTickMinStep);
    return {
      minX: xMin,
      maxX: xMax,
      minY: yMin,
      maxY: yMax,
      xRange: xR,
      yRange: yR,
      projectX: projectXFn,
      projectY: projectYFn,
      xTicks: xt,
      yTicks: yt,
    };
  }, [points, showZeroLine, innerWidth, innerHeight, plotLeft, plotBottom, xTickMinStep, yTickMinStep]);

  const pathData = useMemo(
    () =>
      points
        .map((point, index) => {
          const x = projectX(point.x);
          const y = projectY(point.y);
          return `${index === 0 ? 'M' : 'L'}${x},${y}`;
        })
        .join(' '),
    [points, projectX, projectY],
  );

  const zeroY = projectY(0);

  const handleMouseMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const scaleX = chartWidth / rect.width;
    const mouseX = (event.clientX - rect.left) * scaleX;
    const ratio = (mouseX - plotLeft) / innerWidth;
    const clampedRatio = Math.min(1, Math.max(0, ratio));
    const targetX = minX + clampedRatio * xRange;
    let nearest = points[0];
    let minDelta = Math.abs(nearest.x - targetX);
    for (const point of points) {
      const delta = Math.abs(point.x - targetX);
      if (delta < minDelta) {
        nearest = point;
        minDelta = delta;
      }
    }
    setHover({ x: projectX(nearest.x), y: projectY(nearest.y) });
    setTooltip({
      x: nearest.x,
      y: nearest.y,
      label: nearest.label,
      screenX: event.clientX,
      screenY: event.clientY - 12,
    });
  };

  const handleMouseLeave = () => {
    setHover(null);
    setTooltip(null);
  };

  return (
    <Box
      position="relative"
      bg="blackAlpha.500"
      borderRadius="md"
      borderWidth="1px"
      borderColor={highlighted ? 'brand.300' : 'whiteAlpha.200'}
      px={4}
      py={4}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${chartWidth} ${height}`}
        width="100%"
        height={height}
        preserveAspectRatio="xMidYMid meet"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {showZeroLine && zeroY >= plotTop && zeroY <= plotBottom && (
          <line x1={plotLeft} y1={zeroY} x2={plotRight} y2={zeroY} stroke="#718096" strokeDasharray="4 4" strokeWidth={1} />
        )}
        {xTicks.map((tick) => {
          const x = projectX(tick);
          return <line key={`grid-x-${tick}`} x1={x} y1={plotTop} x2={x} y2={plotBottom} stroke="rgba(255,255,255,0.08)" />;
        })}
        {yTicks.map((tick) => {
          const y = projectY(tick);
          return <line key={`grid-y-${tick}`} x1={plotLeft} y1={y} x2={plotRight} y2={y} stroke="rgba(255,255,255,0.08)" />;
        })}
        {hover && (
          <line x1={hover.x} y1={plotTop} x2={hover.x} y2={plotBottom} stroke="rgba(255,255,255,0.25)" strokeDasharray="4 4" />
        )}
        <path d={pathData} fill="none" stroke={stroke} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
        <line x1={plotLeft} y1={plotBottom} x2={plotRight} y2={plotBottom} stroke="rgba(255,255,255,0.3)" />
        <line x1={plotLeft} y1={plotTop} x2={plotLeft} y2={plotBottom} stroke="rgba(255,255,255,0.3)" />
        {xTicks.map((tick) => {
          const x = projectX(tick);
          return (
            <g key={`x-${tick}`}>
              <line x1={x} y1={plotBottom} x2={x} y2={plotBottom + 6} stroke="rgba(255,255,255,0.3)" />
              <text
                x={x}
                y={plotBottom + 20}
                fill="#CBD5F5"
                fontSize={11}
                fontFamily={AXIS_FONT}
                textAnchor="middle"
              >
                {Math.round(tick).toLocaleString()}
              </text>
            </g>
          );
        })}
        {yTicks.map((tick) => {
          const y = projectY(tick);
          return (
            <g key={`y-${tick}`}>
              <line x1={plotLeft - 6} y1={y} x2={plotLeft} y2={y} stroke="rgba(255,255,255,0.3)" />
              <text
                x={plotLeft - 10}
                y={y + 4}
                fill="#CBD5F5"
                fontSize={11}
                fontFamily={AXIS_FONT}
                textAnchor="end"
              >
                {Math.round(tick).toLocaleString()}
              </text>
            </g>
          );
        })}
        <text
          x={plotLeft + innerWidth / 2}
          y={plotBottom + 40}
          fill="white"
          fontSize={12}
          fontFamily={AXIS_FONT}
          textAnchor="middle"
        >
          {xLabel}
        </text>
        <text
          x={plotLeft - 52}
          y={plotTop + innerHeight / 2}
          fill="white"
          fontSize={12}
          fontFamily={AXIS_FONT}
          textAnchor="middle"
          transform={`rotate(-90 ${plotLeft - 52} ${plotTop + innerHeight / 2})`}
        >
          {yLabel}
        </text>
      </svg>
      {tooltip && (
        <Box
          position="fixed"
          left={tooltip.screenX + 12}
          top={tooltip.screenY}
          bg="gray.900"
          borderRadius="md"
          px={3}
          py={2}
          borderWidth="1px"
          borderColor="whiteAlpha.300"
          color="white"
          fontSize="xs"
          pointerEvents="none"
          zIndex={1000}
        >
          {tooltip.label ? (
            <>
              <div>Size Bucket: {tooltip.label}</div>
              <div>{yLabel}: {tooltip.y.toFixed(2)}</div>
            </>
          ) : (
            <>
              <div>
                {xLabel}:{' '}
                {xLabel.includes('%')
                  ? `${tooltip.x.toFixed(1)}%`
                  : Math.round(tooltip.x).toLocaleString()}
              </div>
              <div>
                {yLabel}: {tooltip.y.toFixed(2)}
              </div>
            </>
          )}
        </Box>
      )}
    </Box>
  );
};

export default LineChart;
