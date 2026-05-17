const PADDING = 1;

export function hasSparklineData(
  values: (number | null)[] | undefined,
): values is (number | null)[] {
  return (values?.filter((v) => v !== null).length ?? 0) >= 2;
}

export function Sparkline({
  values,
  width = 60,
  height = 16,
  refValue,
}: {
  values: (number | null)[];
  width?: number;
  height?: number;
  refValue?: number | null;
}) {
  const nums = values.filter((v): v is number => v !== null);
  if (nums.length < 2) return null;

  const allNums = refValue != null ? [...nums, refValue] : nums;
  const min = Math.min(...allNums);
  const max = Math.max(...allNums);
  const range = max - min;
  const drawH = height - 2 * PADDING;

  function toY(v: number): number {
    return range === 0
      ? height / 2
      : PADDING + drawH - ((v - min) / range) * drawH;
  }

  const points = values
    .map((v, i) => {
      if (v === null) return null;
      const x = (i / (values.length - 1)) * width;
      return `${x.toFixed(1)},${toY(v).toFixed(1)}`;
    })
    .filter((p): p is string => p !== null)
    .join(" ");

  const refY = refValue != null ? toY(refValue) : null;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
    >
      {refY != null && (
        <line
          x1={0}
          y1={refY.toFixed(1)}
          x2={width}
          y2={refY.toFixed(1)}
          stroke="currentColor"
          strokeWidth={1}
          strokeDasharray="2 2"
          opacity={0.5}
        />
      )}
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
