import type { Activity } from "@prisma/client";

type Props = {
  activities: Activity[];
};

function fmtDuration(min: number | null): string {
  if (min == null) return "—";
  if (min < 60) return `${Math.round(min)}m`;
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
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
