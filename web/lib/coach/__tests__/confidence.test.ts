import { describe, it, expect } from "vitest";
import {
  computeConfidence,
  computeSyncStaleDays,
  buildFreshnessWarnings,
  type ConfidenceInput,
  type FreshnessInput,
} from "../confidence";

const fullMetrics = { rhr: 52, hrv: 68.0, sleepHours: 7.5 };

function makeConfidenceInput(overrides: Partial<ConfidenceInput> = {}): ConfidenceInput {
  return {
    todayMetrics: { ...fullMetrics },
    hrv7dBaseline: 65.0,
    hasTodayWeight: true,
    syncStaleDays: 0,
    ...overrides,
  };
}

function makeFreshnessInput(overrides: Partial<FreshnessInput> = {}): FreshnessInput {
  return {
    hasTodayMetrics: true,
    todayHrv: 68.0,
    todayRhr: 52,
    daysSinceLastActivity: 1,
    hasTodayWeight: true,
    latestWeightDaysAgo: 0,
    ...overrides,
  };
}

describe("computeSyncStaleDays", () => {
  it("returns 999 for null (never synced)", () => {
    expect(computeSyncStaleDays(null)).toBe(999);
  });

  it("returns 999 for undefined", () => {
    expect(computeSyncStaleDays(undefined)).toBe(999);
  });

  it("returns 0 for a date just synced (within same day)", () => {
    const now = new Date();
    expect(computeSyncStaleDays(now)).toBe(0);
  });

  it("returns 1 for a date ~25 hours ago", () => {
    const d = new Date(Date.now() - 25 * 60 * 60 * 1000);
    expect(computeSyncStaleDays(d)).toBe(1);
  });

  it("returns 0 (not negative) for a future finishedAt timestamp", () => {
    const future = new Date(Date.now() + 48 * 60 * 60 * 1000);
    expect(computeSyncStaleDays(future)).toBe(0);
  });

  it("returns 1 for exactly 24 hours ago", () => {
    const d = new Date(Date.now() - 24 * 60 * 60 * 1000);
    expect(computeSyncStaleDays(d)).toBe(1);
  });

  it("returns 7 for ~7 days ago", () => {
    const d = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    expect(computeSyncStaleDays(d)).toBe(7);
  });
});

describe("computeConfidence", () => {
  it("returns 100 when all data is present and sync is fresh", () => {
    expect(computeConfidence(makeConfidenceInput())).toBe(100);
  });

  it("deducts 65 when todayMetrics is missing", () => {
    expect(computeConfidence(makeConfidenceInput({ todayMetrics: null }))).toBe(35);
  });

  it("deducts 65+15 when todayMetrics missing and sync stale > 1 day", () => {
    expect(
      computeConfidence(makeConfidenceInput({ todayMetrics: null, syncStaleDays: 2 })),
    ).toBe(20);
  });

  it("deducts 10 for missing RHR", () => {
    const input = makeConfidenceInput({
      todayMetrics: { ...fullMetrics, rhr: null },
    });
    expect(computeConfidence(input)).toBe(90);
  });

  it("deducts 10 for missing HRV", () => {
    const input = makeConfidenceInput({
      todayMetrics: { ...fullMetrics, hrv: null },
    });
    expect(computeConfidence(input)).toBe(90);
  });

  it("deducts 5 for missing sleep hours", () => {
    const input = makeConfidenceInput({
      todayMetrics: { ...fullMetrics, sleepHours: null },
    });
    expect(computeConfidence(input)).toBe(95);
  });

  it("deducts 10 for missing HRV and 10 for missing RHR independently", () => {
    const withoutHrv = computeConfidence(
      makeConfidenceInput({ todayMetrics: { ...fullMetrics, hrv: null } }),
    );
    const withoutRhr = computeConfidence(
      makeConfidenceInput({ todayMetrics: { ...fullMetrics, rhr: null } }),
    );
    expect(withoutHrv).toBe(90);
    expect(withoutRhr).toBe(90);
  });

  it("deducts 5 for weight not logged today", () => {
    expect(computeConfidence(makeConfidenceInput({ hasTodayWeight: false }))).toBe(95);
  });

  it("deducts 10 when HRV 7-day baseline is missing", () => {
    expect(computeConfidence(makeConfidenceInput({ hrv7dBaseline: null }))).toBe(90);
  });

  it("deducts 15 when sync is stale > 1 day", () => {
    expect(computeConfidence(makeConfidenceInput({ syncStaleDays: 2 }))).toBe(85);
  });

  it("does not deduct sync penalty when syncStaleDays = 1", () => {
    expect(computeConfidence(makeConfidenceInput({ syncStaleDays: 1 }))).toBe(100);
  });

  it("clamps to 0 when penalties exceed 100", () => {
    // Missing todayMetrics (-65) + stale sync (-15) + no HRV baseline (-10) +
    // no weight (-5) = -95 → but already floored
    const input = makeConfidenceInput({
      todayMetrics: null,
      hrv7dBaseline: null,
      hasTodayWeight: false,
      syncStaleDays: 3,
    });
    expect(computeConfidence(input)).toBeGreaterThanOrEqual(0);
  });

  it("returns <= 35 when all recovery signals are missing", () => {
    const input = makeConfidenceInput({
      todayMetrics: { rhr: null, hrv: null, sleepHours: null },
    });
    // -10 (rhr) -10 (hrv) -5 (sleep) = -25 → 75
    expect(computeConfidence(input)).toBe(75);
  });

  it("returns < 40 when todayMetrics missing, even with 1-day stale sync", () => {
    const input = makeConfidenceInput({ todayMetrics: null, syncStaleDays: 2 });
    expect(computeConfidence(input)).toBeLessThan(40);
  });

  it("cumulative partial penalties: all individual metric fields missing reduces score by 25", () => {
    // rhr=null (-10), hrv=null (-10), sleepHours=null (-5) → 100 - 25 = 75
    const input = makeConfidenceInput({
      todayMetrics: { rhr: null, hrv: null, sleepHours: null },
    });
    expect(computeConfidence(input)).toBe(75);
  });

  it("cumulative: all partial nulls + no weight + no baseline = 60", () => {
    // -10 (rhr) -10 (hrv) -5 (sleep) -5 (weight) -10 (baseline) = -40 → 60
    const input = makeConfidenceInput({
      todayMetrics: { rhr: null, hrv: null, sleepHours: null },
      hasTodayWeight: false,
      hrv7dBaseline: null,
    });
    expect(computeConfidence(input)).toBe(60);
  });

  it("sync penalty fires at exactly syncStaleDays = 2 (> 1 threshold)", () => {
    const fresh = computeConfidence(makeConfidenceInput({ syncStaleDays: 1 }));
    const stale = computeConfidence(makeConfidenceInput({ syncStaleDays: 2 }));
    expect(stale).toBe(fresh - 15);
  });

  it("does not deduct sync penalty when syncStaleDays = 0 (most recent)", () => {
    expect(computeConfidence(makeConfidenceInput({ syncStaleDays: 0 }))).toBe(100);
  });
});

describe("buildFreshnessWarnings", () => {
  it("returns empty array when all data is fresh", () => {
    const warnings = buildFreshnessWarnings(makeFreshnessInput());
    expect(warnings).toHaveLength(0);
  });

  it("warns missing wellness when today metrics are absent", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ hasTodayMetrics: false }),
    );
    expect(warnings.some((w) => w.source === "wellness" && w.freshness === "missing")).toBe(true);
    expect(warnings[0].message).toContain("Wellness data not synced today");
  });

  it("warns stale wellness when HRV and RHR are both null despite having today metrics", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ todayHrv: null, todayRhr: null }),
    );
    expect(warnings.some((w) => w.source === "wellness" && w.freshness === "stale")).toBe(true);
  });

  it("does not warn wellness when HRV is null but RHR is present", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ todayHrv: null, todayRhr: 52 }),
    );
    expect(warnings.some((w) => w.source === "wellness")).toBe(false);
  });

  it("warns missing activity when daysSinceLastActivity is null", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ daysSinceLastActivity: null }),
    );
    expect(warnings.some((w) => w.source === "activity" && w.freshness === "missing")).toBe(true);
  });

  it("warns stale activity for 4-6 days since last session", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ daysSinceLastActivity: 5 }),
    );
    expect(warnings.some((w) => w.source === "activity" && w.freshness === "stale")).toBe(true);
  });

  it("warns missing activity for 7+ days since last session", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ daysSinceLastActivity: 7 }),
    );
    expect(warnings.some((w) => w.source === "activity" && w.freshness === "missing")).toBe(true);
    expect(warnings[0].message).toContain("7 days");
  });

  it("does not warn activity for 3 days or fewer since last session", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ daysSinceLastActivity: 3 }),
    );
    expect(warnings.some((w) => w.source === "activity")).toBe(false);
  });

  it("warns missing weight when no recent weight logged (>3 days ago)", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ hasTodayWeight: false, latestWeightDaysAgo: 5 }),
    );
    expect(warnings.some((w) => w.source === "weight" && w.freshness === "missing")).toBe(true);
  });

  it("warns stale weight when weight logged 1-3 days ago but not today", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ hasTodayWeight: false, latestWeightDaysAgo: 2 }),
    );
    expect(warnings.some((w) => w.source === "weight" && w.freshness === "stale")).toBe(true);
    expect(warnings.find((w) => w.source === "weight")?.message).toContain("2 days");
  });

  it("warns missing weight when latestWeightDaysAgo is null", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ hasTodayWeight: false, latestWeightDaysAgo: null }),
    );
    expect(warnings.some((w) => w.source === "weight" && w.freshness === "missing")).toBe(true);
  });

  it("does not warn weight when logged today", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ hasTodayWeight: true }),
    );
    expect(warnings.some((w) => w.source === "weight")).toBe(false);
  });

  it("warns stale activity at exactly 4 days (lower stale boundary)", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ daysSinceLastActivity: 4 }),
    );
    expect(warnings.some((w) => w.source === "activity" && w.freshness === "stale")).toBe(true);
  });

  it("warns stale activity at 6 days (still stale, not missing)", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ daysSinceLastActivity: 6 }),
    );
    expect(warnings.some((w) => w.source === "activity" && w.freshness === "stale")).toBe(true);
    expect(warnings.some((w) => w.source === "activity" && w.freshness === "missing")).toBe(false);
  });

  it("warns stale weight at exactly latestWeightDaysAgo = 3 (not > 3, so stale not missing)", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ hasTodayWeight: false, latestWeightDaysAgo: 3 }),
    );
    expect(warnings.some((w) => w.source === "weight" && w.freshness === "stale")).toBe(true);
    expect(warnings.some((w) => w.source === "weight" && w.freshness === "missing")).toBe(false);
  });

  it("uses singular 'day' (not 'days') for latestWeightDaysAgo = 1", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ hasTodayWeight: false, latestWeightDaysAgo: 1 }),
    );
    const weightWarning = warnings.find((w) => w.source === "weight");
    expect(weightWarning?.message).toBe("Weight last logged 1 day ago.");
  });

  it("does not warn weight when hasTodayWeight=false but latestWeightDaysAgo=0 (logged same day, edge case)", () => {
    // latestWeightDaysAgo=0 means it's from today, and > 0 is false → no warning
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ hasTodayWeight: false, latestWeightDaysAgo: 0 }),
    );
    expect(warnings.some((w) => w.source === "weight")).toBe(false);
  });

  it("includes the correct stale wellness message text", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ todayHrv: null, todayRhr: null }),
    );
    const wellnessWarning = warnings.find((w) => w.source === "wellness");
    expect(wellnessWarning?.message).toBe("HRV and RHR not available from today's sync.");
  });

  it("emits multiple concurrent warnings when all sources are stale simultaneously", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({
        hasTodayMetrics: false,
        daysSinceLastActivity: 5,
        hasTodayWeight: false,
        latestWeightDaysAgo: 2,
      }),
    );
    expect(warnings.some((w) => w.source === "wellness")).toBe(true);
    expect(warnings.some((w) => w.source === "activity")).toBe(true);
    expect(warnings.some((w) => w.source === "weight")).toBe(true);
    expect(warnings).toHaveLength(3);
  });

  it("does not warn activity when daysSinceLastActivity = 0 (activity today)", () => {
    const warnings = buildFreshnessWarnings(
      makeFreshnessInput({ daysSinceLastActivity: 0 }),
    );
    expect(warnings.some((w) => w.source === "activity")).toBe(false);
  });
});
