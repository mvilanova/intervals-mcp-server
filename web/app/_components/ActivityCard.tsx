import type { Activity } from "@prisma/client";

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
    <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
      <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">
        Today&apos;s training
      </h2>
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
    </section>
  );
}
