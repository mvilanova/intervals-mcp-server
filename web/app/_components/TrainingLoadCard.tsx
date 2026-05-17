import type { DailyMetrics } from "@prisma/client";
import { hasSparklineData, Sparkline } from "./Sparkline";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type Props = {
  today: DailyMetrics | null;
  yesterday: DailyMetrics | null;
  dailyMetrics14d?: DailyMetrics[];
};

function delta(today: number | null, prev: number | null): string | null {
  if (today == null || prev == null) return null;
  const d = today - prev;
  if (Math.abs(d) < 0.05) return "±0";
  const sign = d > 0 ? "+" : "";
  return `${sign}${d.toFixed(1)}`;
}

function fmt(v: number | null, digits = 1): string {
  return v == null ? "—" : v.toFixed(digits);
}

export function TrainingLoadCard({ today, yesterday, dailyMetrics14d }: Props) {
  const ctlDelta = delta(today?.ctl ?? null, yesterday?.ctl ?? null);
  const atlDelta = delta(today?.atl ?? null, yesterday?.atl ?? null);
  const ramp = today?.rampRate;
  const ctlSpark = dailyMetrics14d?.map((m) => m.ctl ?? null);
  const atlSpark = dailyMetrics14d?.map((m) => m.atl ?? null);
  const rampSpark = dailyMetrics14d?.map((m) => m.rampRate ?? null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Training load</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2">
          <Metric
            label="CTL"
            value={fmt(today?.ctl ?? null)}
            delta={ctlDelta}
            sparkValues={ctlSpark}
          />
          <Metric
            label="ATL"
            value={fmt(today?.atl ?? null)}
            delta={atlDelta}
            sparkValues={atlSpark}
          />
          <Metric
            label="Ramp"
            value={ramp == null ? "—" : `${ramp.toFixed(1)}`}
            delta={null}
            sparkValues={rampSpark}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  delta,
  sparkValues,
}: {
  label: string;
  value: string;
  delta: string | null;
  sparkValues?: (number | null)[];
}) {
  return (
    <div>
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      {delta ? (
        <div className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">
          {delta}
        </div>
      ) : null}
      {hasSparklineData(sparkValues) ? (
        <div className="mt-1 text-gray-400 dark:text-gray-500">
          <Sparkline values={sparkValues} />
        </div>
      ) : null}
    </div>
  );
}
