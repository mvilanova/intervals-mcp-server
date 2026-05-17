import type { Activity } from "@prisma/client";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type Props = {
  activities: Activity[];
};

function fmtDuration(min: number | null): string {
  if (min == null) return "—";
  // Round total minutes first so the minute remainder is always 0–59;
  // splitting before rounding could yield e.g. "1h 60m" when min = 119.7.
  const totalMin = Math.round(min);
  if (totalMin < 60) return `${totalMin}m`;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

export function ActivityCard({ activities }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Today&apos;s training</CardTitle>
      </CardHeader>
      <CardContent>
        {activities.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Rest day — no activities logged.
          </p>
        ) : (
          <ul className="space-y-2">
            {activities.map((a) => (
              <li
                key={a.id}
                className="flex items-baseline justify-between text-sm"
              >
                <span className="font-medium">{a.type}</span>
                <span className="text-gray-500 dark:text-gray-400 tabular-nums">
                  {fmtDuration(a.durationMin)}
                  {a.distanceKm != null
                    ? ` · ${a.distanceKm.toFixed(1)} km`
                    : ""}
                  {a.tss != null ? ` · ${a.tss.toFixed(0)} TSS` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
