import { syncIntervals } from "@/lib/sync/intervals";

const HOURS = Number(process.env.SYNC_INTERVAL_HOURS ?? 4);
const PERIOD_MS = Math.max(1, HOURS) * 60 * 60 * 1000;

async function runOnce(mode: "full" | "recent") {
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
  }
}

async function main() {
  console.log(`[cron] starting, period=${HOURS}h`);
  // First run pulls the full 30d window so a fresh deploy backfills history.
  await runOnce("full");
  setInterval(() => {
    void runOnce("recent");
  }, PERIOD_MS);
}

void main();
