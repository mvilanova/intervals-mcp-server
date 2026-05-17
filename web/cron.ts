import { NoUserFoundError, syncIntervals } from "@/lib/sync/intervals";

const HOURS_RAW = Number(process.env.SYNC_INTERVAL_HOURS ?? 4);
const HOURS = Number.isFinite(HOURS_RAW) && HOURS_RAW > 0 ? HOURS_RAW : 4;
const PERIOD_MS = HOURS * 60 * 60 * 1000;

if (HOURS !== HOURS_RAW) {
  console.warn(
    `[cron] Invalid SYNC_INTERVAL_HOURS=${process.env.SYNC_INTERVAL_HOURS}, falling back to 4h`,
  );
}

let shutdownRequested = false;
let resolveShutdown: (() => void) | null = null;
const shutdownPromise = new Promise<void>((resolve) => {
  resolveShutdown = resolve;
});

for (const sig of ["SIGTERM", "SIGINT"] as const) {
  process.on(sig, () => {
    console.log(`[cron] ${sig} received, finishing current sync...`);
    shutdownRequested = true;
    resolveShutdown?.();
  });
}

async function runOnce(mode: "full" | "recent", { rethrow = false } = {}) {
  const startedAt = new Date();
  try {
    const result = await syncIntervals({ mode });
    console.log(
      `[cron] ${startedAt.toISOString()} mode=${mode} ` +
        `wellness=${result.wellnessUpserts} ` +
        `activities=${result.activityUpserts} ` +
        `weight=${result.weightUpserts} ` +
        `errors=${result.errors.length} ` +
        `duration_ms=${result.finishedAt.getTime() - result.startedAt.getTime()}`,
    );
    for (const err of result.errors) console.error(`[cron] error: ${err}`);
  } catch (err) {
    console.error(
      `[cron] ${startedAt.toISOString()} fatal: ${err instanceof Error ? err.message : String(err)}`,
    );
    if (rethrow) throw err;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Start the cron loop that bootstraps and schedules periodic syncs until shutdown.
 *
 * Performs an initial "full" sync then repeatedly runs "recent" syncs at the configured interval.
 * Startup errors representing real infrastructure failures are allowed to propagate, but a
 * `NoUserFoundError` from syncIntervals is logged and suppressed so the cron stays up and retries
 * on the next tick. The loop sleeps for the configured period between runs but wakes early when a
 * shutdown signal is received; after shutdown completes the process exits with code 0.
 */
async function main() {
  console.log(`[cron] starting, period=${HOURS}h`);
  // Bootstrap sync: fail-fast on real infrastructure problems (bad
  // DATABASE_URL, invalid INTERVALS_API_KEY, network unreachable) so the
  // operator notices via the container's restart loop. The single exception
  // is "no user seeded yet" — that's an expected fresh-deploy state, not a
  // misconfiguration, so log it and let the cron stay up until a user is
  // created. The next tick will pick the user up automatically.
  try {
    await runOnce("full", { rethrow: true });
  } catch (err) {
    if (!(err instanceof NoUserFoundError)) throw err;
    console.warn(
      `[cron] bootstrap skipped (${err.message}); will retry on next ${HOURS}h tick`,
    );
  }

  // Sequential awaited delays: a slow sync can never overlap the next tick.
  // Race the sleep against shutdownPromise so SIGTERM/SIGINT can break out
  // mid-wait instead of stalling up to PERIOD_MS.
  while (!shutdownRequested) {
    await Promise.race([sleep(PERIOD_MS), shutdownPromise]);
    if (shutdownRequested) break;
    await runOnce("recent");
  }
  console.log("[cron] shutdown complete");
  process.exit(0);
}

main().catch((err) => {
  console.error(
    `[cron] fatal startup error: ${err instanceof Error ? err.message : String(err)}`,
  );
  process.exit(1);
});
