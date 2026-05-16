import { Suspense } from "react";
import { getTodayBundle } from "@/lib/queries/today";
import { TrainingLoadCard } from "./_components/TrainingLoadCard";
import { RecoveryCard } from "./_components/RecoveryCard";
import { WeightCard } from "./_components/WeightCard";
import { ActivityCard } from "./_components/ActivityCard";
import { SyncStatusPill } from "./_components/SyncStatusPill";
import { WeightForm } from "./_components/WeightForm";
import { MealGrid } from "./_components/MealGrid";
import { DailySummaryCard } from "./_components/DailySummaryCard";

export const dynamic = "force-dynamic";

function formatToday(date: Date): string {
  // todayDate is UTC midnight; without timeZone: "UTC" the formatter uses
  // the runtime tz and renders the previous day for negative offsets.
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export default async function Home() {
  const bundle = await getTodayBundle();

  if (!bundle) {
    return (
      <main className="mx-auto max-w-2xl p-8 space-y-4">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No user seeded yet. Run <code>npm run db:seed</code> in{" "}
          <code>web/</code>.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl p-4 sm:p-8 space-y-4">
      <header className="flex items-baseline justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Today</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {formatToday(bundle.todayDate)}
          </p>
        </div>
        <SyncStatusPill status={bundle.syncStatus} />
      </header>

      <Suspense fallback={<SummarySkeleton />}>
        <DailySummaryCard userId={bundle.user.id} date={bundle.todayDate} />
      </Suspense>

      <WeightCard
        latest={bundle.latestWeight}
        weekAgo={bundle.weightWeekAgo}
        daysAgo={bundle.latestWeightDaysAgo}
        targetWeight={bundle.user.targetWeight}
        targetDate={bundle.user.targetDate}
      />

      <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <WeightForm todayWeight={bundle.todayWeight} />
      </section>

      <MealGrid initial={bundle.todayMealLogs} />

      <TrainingLoadCard today={bundle.today} yesterday={bundle.yesterday} />

      <RecoveryCard
        today={bundle.today}
        baselineRhr={bundle.user.baselineRhr}
      />

      <ActivityCard activities={bundle.todayActivities} />
    </main>
  );
}

function SummarySkeleton() {
  return (
    <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
      <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
        Summary
      </div>
      <div className="h-4 w-3/4 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
    </section>
  );
}
