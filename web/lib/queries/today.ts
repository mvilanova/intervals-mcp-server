import { prisma } from "@/lib/db";
import type {
  Activity,
  DailyMetrics,
  MealLog,
  SyncRun,
  User,
  WeightLog,
} from "@prisma/client";

export type SyncStatus = {
  stale: boolean;
  relative: string;
};

export type TodayBundle = {
  user: User;
  today: DailyMetrics | null;
  yesterday: DailyMetrics | null;
  todayActivities: Activity[];
  todayMealLogs: MealLog[];
  todayWeight: WeightLog | null;
  latestWeight: WeightLog | null;
  weightWeekAgo: WeightLog | null;
  latestSync: Pick<SyncRun, "finishedAt"> | null;
  syncStatus: SyncStatus;
  latestWeightDaysAgo: number | null;
  todayDate: Date;
  hrv7dBaseline: number | null;
  daysSinceLastActivity: number | null;
};

const SYNC_STALE_AFTER_MS = 6 * 60 * 60 * 1000;

function relativeFromNow(date: Date, nowMs: number): string {
  const min = Math.round((nowMs - date.getTime()) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

// Midnight UTC of today's date — matches how the Intervals sync stores
// `@db.Date` rows (sync code does `new Date("YYYY-MM-DD")` which lands at
// 00:00:00 UTC). Keeps date arithmetic and equality joins simple.
function dateOnlyUTC(d: Date = new Date()): Date {
  return new Date(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()),
  );
}

function addDays(d: Date, days: number): Date {
  const out = new Date(d);
  out.setUTCDate(out.getUTCDate() + days);
  return out;
}

export async function getTodayBundle(): Promise<TodayBundle | null> {
  const user = await prisma.user.findFirst({
    orderBy: { createdAt: "asc" },
  });
  if (!user) return null;

  const today = dateOnlyUTC();
  const yesterday = addDays(today, -1);
  const weekAgo = addDays(today, -7);

  const [
    todayMetrics,
    yesterdayMetrics,
    todayActivities,
    todayMealLogs,
    todayWeight,
    latestWeight,
    weightWeekAgo,
    latestSync,
    recentMetricsForHrv,
    latestActivity,
  ] = await Promise.all([
    prisma.dailyMetrics.findUnique({
      where: { userId_date: { userId: user.id, date: today } },
    }),
    prisma.dailyMetrics.findUnique({
      where: { userId_date: { userId: user.id, date: yesterday } },
    }),
    prisma.activity.findMany({
      where: { userId: user.id, date: today },
      orderBy: { tss: "desc" },
    }),
    prisma.mealLog.findMany({
      where: { userId: user.id, date: today },
    }),
    prisma.weightLog.findUnique({
      where: { userId_date: { userId: user.id, date: today } },
    }),
    prisma.weightLog.findFirst({
      where: { userId: user.id },
      orderBy: { date: "desc" },
    }),
    prisma.weightLog.findFirst({
      where: { userId: user.id, date: { lte: weekAgo } },
      orderBy: { date: "desc" },
    }),
    prisma.syncRun.findFirst({
      where: { finishedAt: { not: null } },
      orderBy: { finishedAt: "desc" },
      select: { finishedAt: true },
    }),
    // Rolling 7-day HRV baseline: exclude today to avoid anchoring on today's value.
    // Requires ≥3 non-null HRV values to be meaningful.
    prisma.dailyMetrics.findMany({
      where: { userId: user.id, date: { gte: addDays(today, -7), lt: today } },
      select: { hrv: true },
      orderBy: { date: "desc" },
      take: 7,
    }),
    prisma.activity.findFirst({
      where: { userId: user.id },
      orderBy: { date: "desc" },
      select: { date: true },
    }),
  ]);

  const nowMs = Date.now();
  const syncStatus: SyncStatus = latestSync?.finishedAt
    ? {
        stale: nowMs - latestSync.finishedAt.getTime() > SYNC_STALE_AFTER_MS,
        relative: `synced ${relativeFromNow(latestSync.finishedAt, nowMs)}`,
      }
    : { stale: true, relative: "never synced" };

  const latestWeightDaysAgo = latestWeight
    ? Math.floor((nowMs - latestWeight.date.getTime()) / (1000 * 60 * 60 * 24))
    : null;

  const hrvValues = recentMetricsForHrv
    .map((r) => r.hrv)
    .filter((v): v is number => v != null);
  const hrv7dBaseline =
    hrvValues.length >= 3
      ? hrvValues.reduce((a, b) => a + b, 0) / hrvValues.length
      : null;

  const daysSinceLastActivity = latestActivity
    ? Math.max(0, Math.floor((today.getTime() - latestActivity.date.getTime()) / (1000 * 60 * 60 * 24)))
    : null;

  return {
    user,
    today: todayMetrics,
    yesterday: yesterdayMetrics,
    todayActivities,
    todayMealLogs,
    todayWeight,
    latestWeight,
    weightWeekAgo,
    latestSync,
    syncStatus,
    latestWeightDaysAgo,
    todayDate: today,
    hrv7dBaseline,
    daysSinceLastActivity,
  };
}
