import type { User, WeightLog } from "@prisma/client";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type Props = {
  latest: WeightLog | null;
  weekAgo: WeightLog | null;
  daysAgo: number | null;
  targetWeight: User["targetWeight"];
  targetDate: User["targetDate"];
};

function fmtDelta(d: number): string {
  const sign = d > 0 ? "+" : "";
  return `${sign}${d.toFixed(1)}`;
}

export function WeightCard({
  latest,
  weekAgo,
  daysAgo,
  targetWeight,
  targetDate,
}: Props) {
  const weekDelta =
    latest && weekAgo ? latest.weightKg - weekAgo.weightKg : null;
  const toTarget = latest && targetWeight ? latest.weightKg - targetWeight : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Weight</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-semibold tabular-nums">
            {latest ? latest.weightKg.toFixed(1) : "—"}
          </span>
          <span className="text-sm text-gray-500 dark:text-gray-400">kg</span>
          {latest && daysAgo != null ? (
            <span className="text-xs text-gray-500 dark:text-gray-400 ml-auto">
              {daysAgo === 0 ? "today" : `${daysAgo}d ago`}
            </span>
          ) : null}
        </div>
        <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 tabular-nums">
          <span>
            7d:{" "}
            {weekDelta != null ? (
              <span className={weekDelta < 0 ? "text-emerald-600" : ""}>
                {fmtDelta(weekDelta)} kg
              </span>
            ) : (
              "—"
            )}
          </span>
          <span>
            target:{" "}
            {targetWeight != null
              ? `${targetWeight.toFixed(1)} kg`
              : "—"}
            {toTarget != null ? ` (${fmtDelta(toTarget)})` : ""}
          </span>
        </div>
        {targetDate ? (
          <div className="text-xs text-gray-500 dark:text-gray-400">
            by {targetDate.toISOString().slice(0, 10)}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
