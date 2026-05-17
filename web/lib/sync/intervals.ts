import { prisma } from "@/lib/db";
import { parseUtcDateOnly } from "@/lib/sync/dates";
import { runSourceSync, SourceRunError, SourceRunOutcome } from "@/lib/sync/sourceRun";
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

/**
 * Compute the ISO-formatted oldest and newest date strings for the given sync mode.
 *
 * @param mode - "full" for a 30-day window, "recent" for a 3-day window
 * @returns An object with `oldest` and `newest` as `YYYY-MM-DD` strings (UTC)
 */
function dateWindow(mode: "full" | "recent"): { oldest: string; newest: string } {
  const days = mode === "full" ? 30 : 3;
  const now = new Date();
  const oldest = new Date(now);
  oldest.setUTCDate(oldest.getUTCDate() - days);
  return { oldest: isoDate(oldest), newest: isoDate(now) };
}

// Structured error code so the UI and sourceRun helper can distinguish
// auth failures from schema drift from network timeouts without parsing
// the message string. Keep this enum aligned with the SyncSourceRun
// `errorCode` column.
export type IntervalsErrorCode =
  | "http_error"
  | "timeout"
  | "network_error"
  | "parse_error";

class IntervalsError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly code?: IntervalsErrorCode,
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

function sourceRunError(
  err: unknown,
  partial: SourceRunOutcome,
): SourceRunError {
  const message = err instanceof Error ? err.message : String(err);
  const status =
    err instanceof Error && "status" in err
      ? (err as { status?: number }).status
      : undefined;
  const code =
    err instanceof Error && "code" in err
      ? (err as { code?: string }).code
      : undefined;
  return new SourceRunError(message, { partial, status, code, cause: err });
}

type IntervalsFetchResult = {
  status: number;
  json: unknown;
};

/**
 * Fetches a JSON resource from the Intervals.icu API for the given path and query parameters.
 *
 * @param path - API path to request (appended to the configured Intervals base URL)
 * @param apiKey - Intervals API key used to build the `Authorization` header
 * @param params - Query parameters to include on the request
 * @returns An object containing the HTTP `status` and the parsed JSON response as `json`
 * @throws IntervalsError - Thrown with `code: "http_error"` when the response has a non-OK status (includes response `status`); with `code: "timeout"` when the request exceeds the configured timeout; with `code: "parse_error"` when the response body is not valid JSON; with `code: "network_error"` for other network/fetch errors.
 */
async function intervalsFetch(
  path: string,
  apiKey: string,
  params: Record<string, string>,
): Promise<IntervalsFetchResult> {
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
        "http_error",
      );
    }
    let json: unknown;
    try {
      json = await res.json();
    } catch (err) {
      throw new IntervalsError(
        `Intervals.icu parse error on ${path}: ${err instanceof Error ? err.message : String(err)}`,
        res.status,
        "parse_error",
      );
    }
    return { status: res.status, json };
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new IntervalsError(
        `Intervals.icu request timeout after ${FETCH_TIMEOUT_MS}ms on ${path}`,
        408,
        "timeout",
      );
    }
    // Wrap raw fetch/network errors so the source-run helper can record
    // them with a recognizable code instead of a generic "Error" status.
    if (err instanceof IntervalsError) throw err;
    if (err instanceof Error) {
      throw new IntervalsError(
        `Intervals.icu network error on ${path}: ${err.message}`,
        undefined,
        "network_error",
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

/**
 * Upserts wellness entries into the user's daily metrics and reports counts.
 *
 * Entries that do not contain a parsable date are skipped and not written.
 *
 * @param userId - The target user's ID for the upserts
 * @param entries - Array of wellness entries to upsert into daily metrics
 * @returns An object with `upserted` equal to the number of rows created or updated and `skipped` equal to the number of entries ignored due to missing dates
 */
async function upsertWellness(
  userId: string,
  entries: WellnessEntry[],
): Promise<{ upserted: number; skipped: number }> {
  let upserted = 0;
  let skipped = 0;
  // Counted at the top of each iteration so the catch block can report
  // parsedCount as "rows actually reached" rather than the full input
  // length — otherwise unreached entries get folded into `unchanged` via
  // `parsed - upserted - skipped` and silently overstate the count.
  let processed = 0;
  try {
    for (const entry of entries) {
      processed++;
      const dateStr = wellnessDate(entry);
      if (!dateStr) {
        skipped++;
        continue;
      }
      const date = parseUtcDateOnly(dateStr);
      if (!date) {
        skipped++;
        continue;
      }

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

      const existing = await prisma.dailyMetrics.findUnique({
        where: { userId_date: { userId, date } },
      });

      if (!existing) {
        await prisma.dailyMetrics.create({ data: { userId, date, ...data } });
        upserted++;
        continue;
      }

      const changed = Object.entries(data).some(
        ([key, value]) => existing[key as keyof typeof data] !== value,
      );
      if (changed) {
        await prisma.dailyMetrics.update({
          where: { userId_date: { userId, date } },
          data,
        });
        upserted++;
      }
    }
  } catch (err) {
    throw sourceRunError(err, {
      fetchedCount: entries.length,
      parsedCount: processed,
      upsertedCount: upserted,
      skippedCount: skipped,
    });
  }
  return { upserted, skipped };
}

// Returns the count of wellness entries that *carry* a weight reading,
// alongside how many of those we upserted vs. skipped (because a manual
// entry already exists). The `weight` source uses `withWeight` as its
// `parsedCount` so the UI shows "fetched: 5, written: 2, unchanged: 3"
/**
 * Upserts weight records derived from Intervals wellness entries into the database.
 *
 * For each wellness entry that includes a weight, attempts an atomic update of an existing
 * "from intervals" weight row for the same user/date; if none exists, attempts to create
 * a new "from intervals" row. Manual weight entries (rows whose notes are not "from intervals")
 * are never overwritten; concurrent manual inserts are detected via the unique constraint and
 * cause the entry to be skipped.
 *
 * @param userId - ID of the user to upsert weight records for
 * @param entries - Normalized wellness entries from which weight values are read
 * @returns An object with:
 *  - `withWeight`: number of wellness entries that contained a weight value
 *  - `upserted`: number of database rows successfully updated or created from those weights
 *  - `skipped`: number of entries skipped due to missing/unparseable dates. Manual-entry
 *     conflicts (P2002) are intentionally NOT counted here — they flow into `unchanged`
 *     via the `parsed - upserted - skipped` accounting so the UI labels them correctly.
 */
async function upsertWeightFromWellness(
  userId: string,
  entries: WellnessEntry[],
): Promise<{ withWeight: number; upserted: number; skipped: number }> {
  const totalWithWeight = entries.filter((entry) => entry.weight != null).length;
  let withWeight = 0;
  let upserted = 0;
  let skipped = 0;
  let processed = 0;
  try {
    for (const entry of entries) {
      if (entry.weight == null) continue;
      processed++;
      // Count every weight-carrying entry as "fetched" before any guard so
      // parsedCount in the source run row matches the math invariant
      // `unchanged = parsed - upserted - skipped`. Otherwise an invalid
      // date would produce `fetched: 0, skipped: 1` — impossible totals.
      withWeight++;
      const dateStr = wellnessDate(entry);
      if (!dateStr) {
        skipped++;
        continue;
      }
      const date = parseUtcDateOnly(dateStr);
      if (!date) {
        skipped++;
        continue;
      }

      const existing = await prisma.weightLog.findUnique({
        where: { userId_date: { userId, date } },
      });

      if (!existing) {
        try {
          await prisma.weightLog.create({
            data: {
              userId,
              date,
              weightKg: entry.weight,
              notes: "from intervals",
            },
          });
          upserted++;
        } catch (err) {
          if (
            err instanceof Error &&
            "code" in err &&
            (err as { code?: string }).code === "P2002"
          ) {
            continue;
          }
          throw err;
        }
        continue;
      }

      if (existing.notes !== "from intervals") {
        continue;
      }

      if (existing.weightKg !== entry.weight) {
        await prisma.weightLog.update({
          where: { userId_date: { userId, date } },
          data: { weightKg: entry.weight },
        });
        upserted++;
      }
    }
  } catch (err) {
    // `withWeight` already counts only weight-carrying entries that
    // have been reached in the loop, so it doubles as the processed
    // counter here — no separate variable needed.
    throw sourceRunError(err, {
      fetchedCount: totalWithWeight,
      parsedCount: processed,
      upsertedCount: upserted,
      skippedCount: skipped,
    });
  }
  return { withWeight, upserted, skipped };
}

/**
 * Upserts Intervals.icu activity entries into the database for the given user.
 *
 * @param userId - The database user id to associate activities with
 * @param entries - Activity entries parsed from the Intervals.icu API
 * @returns An object with `upserted` set to the number of rows created or updated, and `skipped` set to the number of entries omitted because a valid date could not be determined
 */
async function upsertActivities(
  userId: string,
  entries: ActivityEntry[],
): Promise<{ upserted: number; skipped: number }> {
  let upserted = 0;
  let skipped = 0;
  let processed = 0;
  try {
    for (const entry of entries) {
      processed++;
      const intervalsId = String(entry.id);
      const dateStr = activityDate(entry);
      if (!dateStr) {
        skipped++;
        continue;
      }
      const date = parseUtcDateOnly(dateStr);
      if (!date) {
        skipped++;
        continue;
      }

      const data = {
        date,
        type: entry.type ?? "Unknown",
        durationMin: entry.moving_time ?? entry.duration ?? entry.elapsed_time,
        tss: entry.icu_training_load ?? entry.trainingLoad ?? null,
        distanceKm: entry.distance != null ? entry.distance / 1000 : null,
      };
      if (data.durationMin != null) data.durationMin /= 60;

      const existing = await prisma.activity.findUnique({
        where: { userId_intervalsId: { userId, intervalsId } },
      });

      if (!existing) {
        await prisma.activity.create({
          data: { userId, intervalsId, ...data },
        });
        upserted++;
        continue;
      }

      const changed =
        existing.date.getTime() !== date.getTime() ||
        existing.type !== data.type ||
        existing.durationMin !== data.durationMin ||
        existing.tss !== data.tss ||
        existing.distanceKm !== data.distanceKm;

      if (changed) {
        await prisma.activity.update({
          where: { userId_intervalsId: { userId, intervalsId } },
          data,
        });
        upserted++;
      }
    }
  } catch (err) {
    throw sourceRunError(err, {
      fetchedCount: entries.length,
      parsedCount: processed,
      upsertedCount: upserted,
      skippedCount: skipped,
    });
  }
  return { upserted, skipped };
}

/**
 * Syncs wellness, weight, and activity data from Intervals.icu into the Prisma database for the specified time window.
 *
 * @param opts.mode - "full" syncs the last 30 days; "recent" syncs the last 3 days.
 * @param opts.userId - Optional user id to sync into; when omitted the earliest-created user is used.
 * @returns A SyncResult containing per-source upsert counts, `startedAt`/`finishedAt` timestamps, and any recorded errors.
 * @throws Error - If INTERVALS_API_KEY or INTERVALS_ATHLETE_ID are not set in the environment.
 * @throws NoUserFoundError - If no user exists to sync into.
 * @throws Error - If another sync is already in progress (or if a retry after reclaiming a stale lock still detects a concurrent run).
 */
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

  // Wellness owns the API call; weight piggybacks on its payload. The
  // fetch lives inside the wellness `run` callback so the SyncSourceRun
  // row is created BEFORE the 30s HTTP call starts — otherwise a crash
  // mid-fetch leaves no per-source evidence and /admin/sync can't show
  // wellness/weight as in-flight.
  //
  // `wellnessPayloadError` is set ONLY when fetch or parse fails — i.e.
  // when weight genuinely has nothing to work with. A failure later in
  // upsertWellness (DB write error) does NOT propagate to weight: the
  // payload is fine, only the wellness DB write failed, so weight can
  // still run independently. This preserves the per-source isolation
  // contract. Storing the original error instance (not a recoded copy)
  // keeps IntervalsError.code/status intact on the weight row.
  let wellness: WellnessEntry[] | null = null;
  let wellnessHttpStatus: number | undefined;
  let wellnessPayloadError: Error | null = null;

  const wellnessResult = await runSourceSync({
    syncRunId: run.id,
    source: "wellness",
    requestedFrom: oldest,
    requestedTo: newest,
    run: async () => {
      let wellnessRes: { status: number; json: unknown };
      try {
        wellnessRes = await intervalsFetch(
          `/athlete/${athleteId}/wellness`,
          apiKey,
          { oldest, newest },
        );
      } catch (err) {
        wellnessPayloadError =
          err instanceof Error ? err : new Error(String(err));
        throw err;
      }
      wellnessHttpStatus = wellnessRes.status;
      try {
        wellness = normalizeWellness(wellnessRes.json);
      } catch (err) {
        const wrapped = new IntervalsError(
          `wellness parse error: ${err instanceof Error ? err.message : String(err)}`,
          wellnessRes.status,
          "parse_error",
        );
        wellnessPayloadError = wrapped;
        throw wrapped;
      }
      // Past this point, weight has the payload it needs. An upsert
      // failure here only affects the wellness row, not weight.
      const { upserted, skipped } = await upsertWellness(user.id, wellness);
      return {
        fetchedCount: wellness.length,
        parsedCount: wellness.length,
        upsertedCount: upserted,
        skippedCount: skipped,
        httpStatus: wellnessHttpStatus,
      };
    },
  });
  if (wellnessResult.errorMessage) {
    errors.push(`wellness: ${wellnessResult.errorMessage}`);
  }

  const weightResult = await runSourceSync({
    syncRunId: run.id,
    source: "weight",
    requestedFrom: oldest,
    requestedTo: newest,
    run: async () => {
      if (wellnessPayloadError) throw wellnessPayloadError;
      if (!wellness) throw new Error("wellness payload unavailable");
      const { withWeight, upserted, skipped } = await upsertWeightFromWellness(
        user.id,
        wellness,
      );
      return {
        fetchedCount: withWeight,
        parsedCount: withWeight,
        upsertedCount: upserted,
        skippedCount: skipped,
        httpStatus: wellnessHttpStatus,
      };
    },
  });
  if (weightResult.errorMessage) {
    errors.push(`weight: ${weightResult.errorMessage}`);
  }

  const activitiesResult = await runSourceSync({
    syncRunId: run.id,
    source: "activities",
    requestedFrom: oldest,
    requestedTo: newest,
    run: async () => {
      const activitiesRes = await intervalsFetch(
        `/athlete/${athleteId}/activities`,
        apiKey,
        { oldest, newest },
      );
      let activities: ActivityEntry[];
      try {
        activities = ActivityResponse.parse(activitiesRes.json);
      } catch (err) {
        throw new IntervalsError(
          `activities parse error: ${err instanceof Error ? err.message : String(err)}`,
          activitiesRes.status,
          "parse_error",
        );
      }
      const { upserted, skipped } = await upsertActivities(user.id, activities);
      return {
        fetchedCount: activities.length,
        parsedCount: activities.length,
        upsertedCount: upserted,
        skippedCount: skipped,
        httpStatus: activitiesRes.status,
      };
    },
  });
  if (activitiesResult.errorMessage) {
    errors.push(`activities: ${activitiesResult.errorMessage}`);
  }

  const finished = await prisma.syncRun.update({
    where: { id: run.id },
    data: {
      finishedAt: new Date(),
      wellnessUpserts: wellnessResult.upsertedCount,
      activityUpserts: activitiesResult.upsertedCount,
      weightUpserts: weightResult.upsertedCount,
      errors,
    },
  });

  return {
    wellnessUpserts: wellnessResult.upsertedCount,
    activityUpserts: activitiesResult.upsertedCount,
    weightUpserts: weightResult.upsertedCount,
    startedAt: finished.startedAt,
    finishedAt: finished.finishedAt!,
    errors,
  };
}
