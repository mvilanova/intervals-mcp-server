import { syncIntervals } from "@/lib/sync/intervals";

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

async function main() {
  console.log(`[cron] starting, period=${HOURS}h`);
  // Bootstrap sync — if this fails the process exits non-zero via the outer
  // .catch() so the container restarts (or fails the deploy).
  await runOnce("full", { rethrow: true });

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
