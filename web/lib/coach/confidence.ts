// Data freshness and confidence scoring for the coach decision engine.
// These are pure functions with no DB access — callers map from TodayBundle.
//
// Note on per-source freshness: we infer source staleness from data presence
// (no DailyMetrics row = stale wellness) rather than querying SyncSourceRun
// directly. SyncSourceRun tracks sync-run outcomes for observability; what the
// coach needs is "can I use this signal?", which is answered by the data itself.

export type DataFreshness = "fresh" | "stale" | "missing";

export type FreshnessWarning = {
  source: "wellness" | "activity" | "weight";
  freshness: DataFreshness;
  message: string;
};

export type ConfidenceInput = {
  todayMetrics: {
    rhr: number | null;
    hrv: number | null;
    sleepHours: number | null;
  } | null;
  hrv7dBaseline: number | null;
  hasTodayWeight: boolean;
  syncStaleDays: number;
};

export type FreshnessInput = {
  hasTodayMetrics: boolean;
  todayHrv: number | null;
  todayRhr: number | null;
  daysSinceLastActivity: number | null;
  hasTodayWeight: boolean;
  latestWeightDaysAgo: number | null;
};

export function computeSyncStaleDays(finishedAt: Date | null | undefined): number {
  if (!finishedAt) return 999;
  return Math.max(0, Math.floor((Date.now() - finishedAt.getTime()) / (1000 * 60 * 60 * 24)));
}

// Returns 0–100. Penalties from fitness-intelligence-model.md §3.5.
// Weight penalty uses "not logged today" (§1.4 intent) rather than
// "no latestWeight at all" (§3.5 example code) — more conservative.
export function computeConfidence(input: ConfidenceInput): number {
  let score = 100;
  if (!input.todayMetrics) {
    score -= 65;
  } else {
    if (input.todayMetrics.rhr == null) score -= 10;
    if (input.todayMetrics.hrv == null) score -= 10;
    if (input.todayMetrics.sleepHours == null) score -= 5;
  }
  if (!input.hasTodayWeight) score -= 5;
  if (input.hrv7dBaseline == null) score -= 10;
  if (input.syncStaleDays > 1) score -= 15;
  return Math.max(0, score);
}

// Returns human-readable per-source freshness warnings.
// Activity freshness thresholds align with §2.7 training-recency flags.
// Weight / wellness thresholds follow the DataFreshness definition in §1.4.
export function buildFreshnessWarnings(input: FreshnessInput): FreshnessWarning[] {
  const warnings: FreshnessWarning[] = [];

  if (!input.hasTodayMetrics) {
    warnings.push({
      source: "wellness",
      freshness: "missing",
      message: "Wellness data not synced today.",
    });
  } else if (input.todayHrv == null && input.todayRhr == null) {
    warnings.push({
      source: "wellness",
      freshness: "stale",
      message: "HRV and RHR not available from today's sync.",
    });
  }

  if (input.daysSinceLastActivity == null) {
    warnings.push({
      source: "activity",
      freshness: "missing",
      message: "No activity data found.",
    });
  } else if (input.daysSinceLastActivity >= 7) {
    warnings.push({
      source: "activity",
      freshness: "missing",
      message: `No activity logged in ${input.daysSinceLastActivity} days.`,
    });
  } else if (input.daysSinceLastActivity >= 4) {
    warnings.push({
      source: "activity",
      freshness: "stale",
      message: `Last activity was ${input.daysSinceLastActivity} days ago.`,
    });
  }

  if (!input.hasTodayWeight) {
    if (input.latestWeightDaysAgo == null || input.latestWeightDaysAgo > 3) {
      warnings.push({
        source: "weight",
        freshness: "missing",
        message: "No recent weight logged.",
      });
    } else if (input.latestWeightDaysAgo > 0) {
      warnings.push({
        source: "weight",
        freshness: "stale",
        message: `Weight last logged ${input.latestWeightDaysAgo} day${input.latestWeightDaysAgo === 1 ? "" : "s"} ago.`,
      });
    }
  }

  return warnings;
}
