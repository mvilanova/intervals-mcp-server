import { prisma } from "@/lib/db";
import {
  ActivityEntry,
  ActivityResponse,
  SyncResult,
  WellnessEntry,
  WellnessResponse,
} from "@/lib/sync/types";

const BASE_URL =
  process.env.INTERVALS_API_BASE_URL ?? "https://intervals.icu/api/v1";

function basicAuthHeader(apiKey: string): string {
  // Intervals.icu uses HTTP Basic with the literal username "API_KEY".
  // Pattern mirrors src/intervals_mcp_server/api/client.py:130.
  const token = Buffer.from(`API_KEY:${apiKey}`).toString("base64");
  return `Basic ${token}`;
}

function isoDate(d: Date): string {
  // YYYY-MM-DD in UTC. Intervals.icu's `oldest`/`newest` params expect this.
  return d.toISOString().slice(0, 10);
}

function dateWindow(mode: "full" | "recent"): { oldest: string; newest: string } {
  const days = mode === "full" ? 30 : 3;
  const now = new Date();
  const oldest = new Date(now);
  oldest.setUTCDate(oldest.getUTCDate() - days);
  return { oldest: isoDate(oldest), newest: isoDate(now) };
}

class IntervalsError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
  }
}

// Thrown when syncIntervals can't find any User row to sync into. Separate
// from IntervalsError so callers (the cron bootstrap, in particular) can
// match this specific expected-fresh-deploy condition with `instanceof`
// instead of a substring check on the message.
export class NoUserFoundError extends Error {
  constructor() {
    super("No user found to sync into");
    this.name = "NoUserFoundError";
  }
}

const FETCH_TIMEOUT_MS = 30_000;

async function intervalsFetch(
  path: string,
  apiKey: string,
  params: Record<string, string>,
): Promise<unknown> {
  const url = new URL(`${BASE_URL}${path}`);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      headers: {
        Authorization: basicAuthHeader(apiKey),
        Accept: "application/json",
        "User-Agent": "getmAIlean-dashboard/0.1",
      },
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new IntervalsError(
        `Intervals.icu ${res.status} ${res.statusText} on ${path}${body ? `: ${body.slice(0, 200)}` : ""}`,
        res.status,
      );
    }
    return await res.json();
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new IntervalsError(
        `Intervals.icu request timeout after ${FETCH_TIMEOUT_MS}ms on ${path}`,
        408,
      );
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

function normalizeWellness(raw: unknown): WellnessEntry[] {
  const parsed = WellnessResponse.parse(raw);
  if (Array.isArray(parsed)) return parsed;
  // Object keyed by date — copy the key into `id` if missing so downstream
  // doesn't have to track which shape it came from.
  return Object.entries(parsed).map(([dateStr, entry]) => ({
    ...entry,
    id: entry.id ?? dateStr,
  }));
}

function wellnessDate(entry: WellnessEntry): string | null {
  const raw = entry.id ?? entry.date ?? null;
  if (!raw) return null;
  // Already YYYY-MM-DD in athlete's local zone — keep as-is.
  return raw.slice(0, 10);
}

function activityDate(entry: ActivityEntry): string | null {
  const raw = entry.startTime ?? entry.start_date ?? null;
  if (!raw) return null;
  return raw.slice(0, 10);
}

function sleepHoursFrom(entry: WellnessEntry): number | null {
  if (entry.sleepSecs != null) return entry.sleepSecs / 3600;
  if (entry.sleepHours != null) return entry.sleepHours;
  return null;
}

async function upsertWellness(
  userId: string,
  entries: WellnessEntry[],
): Promise<number> {
  let count = 0;
  for (const entry of entries) {
    const dateStr = wellnessDate(entry);
    if (!dateStr) continue;
    const date = new Date(dateStr);

    const data = {
      ctl: entry.ctl ?? null,
      atl: entry.atl ?? null,
      rampRate: entry.rampRate ?? null,
      rhr: entry.restingHR != null ? Math.round(entry.restingHR) : null,
      hrv: entry.hrv ?? null,
      sleepHours: sleepHoursFrom(entry),
      sleepScore: entry.sleepScore != null ? Math.round(entry.sleepScore) : null,
      steps: entry.steps != null ? Math.round(entry.steps) : null,
      kcalConsumed:
        entry.kcalConsumed != null ? Math.round(entry.kcalConsumed) : null,
      carbsGrams: entry.carbohydrates ?? null,
      proteinGrams: entry.protein ?? null,
      fatGrams: entry.fatTotal ?? null,
    };

    await prisma.dailyMetrics.upsert({
      where: { userId_date: { userId, date } },
      update: data,
      create: { userId, date, ...data },
    });
    count++;
  }
  return count;
}

async function upsertWeightFromWellness(
  userId: string,
  entries: WellnessEntry[],
): Promise<number> {
  let count = 0;
  for (const entry of entries) {
    if (entry.weight == null) continue;
    const dateStr = wellnessDate(entry);
    if (!dateStr) continue;
    const date = new Date(dateStr);

    // Atomic update: only touch rows already marked "from intervals".
    // Manual weight entries (notes != "from intervals") are never overwritten,
    // and the where-filter on updateMany makes the check + write atomic.
    const updated = await prisma.weightLog.updateMany({
      where: { userId, date, notes: "from intervals" },
      data: { weightKg: entry.weight },
    });

    if (updated.count > 0) {
      count++;
      continue;
    }

    // No from-intervals row existed. Try to create one. The unique constraint
    // on (userId, date) means this fails if a manual entry was inserted
    // concurrently — in that case we skip, preserving the manual entry.
    try {
      await prisma.weightLog.create({
        data: {
          userId,
          date,
          weightKg: entry.weight,
          notes: "from intervals",
        },
      });
      count++;
    } catch (err) {
      if (
        err instanceof Error &&
        "code" in err &&
        (err as { code?: string }).code === "P2002"
      ) {
        // Manual entry beat us to it; that's the desired behaviour.
        continue;
      }
      throw err;
    }
  }
  return count;
}

async function upsertActivities(
  userId: string,
  entries: ActivityEntry[],
): Promise<number> {
  let count = 0;
  for (const entry of entries) {
    const intervalsId = String(entry.id);
    const dateStr = activityDate(entry);
    if (!dateStr) continue;
    const date = new Date(dateStr);

    const movingSec = entry.moving_time ?? entry.duration ?? entry.elapsed_time;
    const data = {
      date,
      type: entry.type ?? "Unknown",
      durationMin: movingSec != null ? movingSec / 60 : null,
      tss: entry.icu_training_load ?? entry.trainingLoad ?? null,
      distanceKm: entry.distance != null ? entry.distance / 1000 : null,
    };

    await prisma.activity.upsert({
      where: { userId_intervalsId: { userId, intervalsId } },
      update: data,
      create: { userId, intervalsId, ...data },
    });
    count++;
  }
  return count;
}

export async function syncIntervals(opts: {
  mode: "full" | "recent";
  userId?: string;
}): Promise<SyncResult> {
  const apiKey = process.env.INTERVALS_API_KEY;
  const athleteId = process.env.INTERVALS_ATHLETE_ID;
  if (!apiKey || !athleteId) {
    throw new Error(
      "INTERVALS_API_KEY and INTERVALS_ATHLETE_ID must be set in env",
    );
  }

  const user = opts.userId
    ? await prisma.user.findUnique({ where: { id: opts.userId } })
    : await prisma.user.findFirst({ orderBy: { createdAt: "asc" } });
  if (!user) {
    throw new NoUserFoundError();
  }

  // The DB has a partial unique index on SyncRun WHERE finishedAt IS NULL.
  // Concurrent attempts to start a sync hit P2002, which we surface as
  // "already in progress". On P2002 we also try to reclaim a stale lock —
  // if the pending row is older than STALE_RUN_AFTER_MS we mark it failed
  // and retry, so a crashed sync can't block all future syncs forever.
  const STALE_RUN_AFTER_MS = 30 * 60 * 1000;
  const isP2002 = (e: unknown): boolean =>
    e instanceof Error &&
    "code" in e &&
    (e as { code?: string }).code === "P2002";

  let run: { id: string; startedAt: Date };
  try {
    run = await prisma.syncRun.create({ data: { mode: opts.mode } });
  } catch (err) {
    if (!isP2002(err)) throw err;

    const pending = await prisma.syncRun.findFirst({
      where: { finishedAt: null },
      orderBy: { startedAt: "asc" },
    });
    const isStale =
      pending && Date.now() - pending.startedAt.getTime() > STALE_RUN_AFTER_MS;
    if (!isStale) {
      throw new Error("A sync is already in progress");
    }

    await prisma.syncRun.update({
      where: { id: pending.id },
      data: {
        finishedAt: new Date(),
        errors: [
          ...pending.errors,
          `aborted: pending > ${STALE_RUN_AFTER_MS / 60000} min`,
        ],
      },
    });

    try {
      run = await prisma.syncRun.create({ data: { mode: opts.mode } });
    } catch (retryErr) {
      if (isP2002(retryErr)) {
        throw new Error("A sync is already in progress");
      }
      throw retryErr;
    }
  }

  const { oldest, newest } = dateWindow(opts.mode);
  const errors: string[] = [];
  let wellnessUpserts = 0;
  let activityUpserts = 0;
  let weightUpserts = 0;

  try {
    const wellnessRaw = await intervalsFetch(
      `/athlete/${athleteId}/wellness`,
      apiKey,
      { oldest, newest },
    );
    const wellness = normalizeWellness(wellnessRaw);
    wellnessUpserts = await upsertWellness(user.id, wellness);
    weightUpserts = await upsertWeightFromWellness(user.id, wellness);
  } catch (err) {
    errors.push(`wellness: ${err instanceof Error ? err.message : String(err)}`);
  }

  try {
    const activitiesRaw = await intervalsFetch(
      `/athlete/${athleteId}/activities`,
      apiKey,
      { oldest, newest },
    );
    const activities = ActivityResponse.parse(activitiesRaw);
    activityUpserts = await upsertActivities(user.id, activities);
  } catch (err) {
    errors.push(
      `activities: ${err instanceof Error ? err.message : String(err)}`,
    );
  }

  const finished = await prisma.syncRun.update({
    where: { id: run.id },
    data: {
      finishedAt: new Date(),
      wellnessUpserts,
      activityUpserts,
      weightUpserts,
      errors,
    },
  });

  return {
    wellnessUpserts,
    activityUpserts,
    weightUpserts,
    startedAt: finished.startedAt,
    finishedAt: finished.finishedAt!,
    errors,
  };
}
