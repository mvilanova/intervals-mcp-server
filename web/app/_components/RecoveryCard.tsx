import type { DailyMetrics } from "@prisma/client";
import { hasSparklineData, Sparkline } from "./Sparkline";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type Props = {
  today: DailyMetrics | null;
  baselineRhr: number | null;
  dailyMetrics14d?: DailyMetrics[];
};

function rhrDelta(rhr: number | null, baseline: number | null): string | null {
  if (rhr == null || baseline == null) return null;
  const d = rhr - baseline;
  if (d === 0) return "= baseline";
  const sign = d > 0 ? "+" : "";
  return `${sign}${d} vs baseline`;
}

export function RecoveryCard({ today, baselineRhr, dailyMetrics14d }: Props) {
  const sleepHours = today?.sleepHours;
  const sleepScore = today?.sleepScore;
  const rhrSpark = dailyMetrics14d?.map((m) => m.rhr ?? null);
  const hrvSpark = dailyMetrics14d?.map((m) => m.hrv ?? null);
  const sleepSpark = dailyMetrics14d?.map((m) => m.sleepHours ?? null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recovery</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">RHR</div>
            <div className="text-2xl font-semibold tabular-nums">
              {today?.rhr ?? "—"}
            </div>
            {rhrDelta(today?.rhr ?? null, baselineRhr) ? (
              <div className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">
                {rhrDelta(today?.rhr ?? null, baselineRhr)}
              </div>
            ) : null}
            {hasSparklineData(rhrSpark) ? (
              <div className="mt-1 text-gray-400 dark:text-gray-500">
                <Sparkline values={rhrSpark} />
              </div>
            ) : null}
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">HRV</div>
            <div className="text-2xl font-semibold tabular-nums">
              {today?.hrv != null ? today.hrv.toFixed(0) : "—"}
            </div>
            {hasSparklineData(hrvSpark) ? (
              <div className="mt-1 text-gray-400 dark:text-gray-500">
                <Sparkline values={hrvSpark} />
              </div>
            ) : null}
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Sleep</div>
            <div className="text-2xl font-semibold tabular-nums">
              {sleepHours != null ? `${sleepHours.toFixed(1)}h` : "—"}
            </div>
            {sleepScore != null ? (
              <div className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">
                score {sleepScore}
              </div>
            ) : null}
            {hasSparklineData(sleepSpark) ? (
              <div className="mt-1 text-gray-400 dark:text-gray-500">
                <Sparkline values={sleepSpark} />
              </div>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
