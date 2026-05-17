import type { DailyMetrics } from "@prisma/client";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type Props = {
  today: DailyMetrics | null;
  yesterday: DailyMetrics | null;
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

export function TrainingLoadCard({ today, yesterday }: Props) {
  const ctlDelta = delta(today?.ctl ?? null, yesterday?.ctl ?? null);
  const atlDelta = delta(today?.atl ?? null, yesterday?.atl ?? null);
  const ramp = today?.rampRate;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Training load</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2">
          <Metric label="CTL" value={fmt(today?.ctl ?? null)} delta={ctlDelta} />
          <Metric label="ATL" value={fmt(today?.atl ?? null)} delta={atlDelta} />
          <Metric
            label="Ramp"
            value={ramp == null ? "—" : `${ramp.toFixed(1)}`}
            delta={null}
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
}: {
  label: string;
  value: string;
  delta: string | null;
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
    </div>
  );
}
