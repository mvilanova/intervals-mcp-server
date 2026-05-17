import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const mocks = vi.hoisted(() => {
  const mockPrisma = {
    user: { findFirst: vi.fn() },
    dailyMetrics: { findUnique: vi.fn(), findMany: vi.fn() },
    activity: { findMany: vi.fn(), findFirst: vi.fn() },
    mealLog: { findMany: vi.fn() },
    weightLog: {
      findUnique: vi.fn(),
      findFirst: vi.fn(),
      findMany: vi.fn(),
    },
    syncRun: { findFirst: vi.fn() },
  };
  return { mockPrisma };
});

vi.mock("@/lib/db", () => ({ prisma: mocks.mockPrisma }));

import { getTodayBundle } from "../today";

const MOCK_USER = {
  id: "user-1",
  email: "test@example.com",
  createdAt: new Date("2024-01-01"),
  updatedAt: new Date("2024-01-01"),
  targetWeight: null,
  targetDate: null,
  baselineRhr: null,
};

// Fixed "now" for deterministic tests: 2024-06-15 12:00:00 UTC
const FIXED_NOW = new Date("2024-06-15T12:00:00.000Z").getTime();

function setupDefaultMocks() {
  mocks.mockPrisma.user.findFirst.mockResolvedValue(MOCK_USER);
  mocks.mockPrisma.dailyMetrics.findUnique.mockResolvedValue(null);
  mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValue([]);
  mocks.mockPrisma.activity.findMany.mockResolvedValue([]);
  mocks.mockPrisma.activity.findFirst.mockResolvedValue(null);
  mocks.mockPrisma.mealLog.findMany.mockResolvedValue([]);
  mocks.mockPrisma.weightLog.findUnique.mockResolvedValue(null);
  mocks.mockPrisma.weightLog.findFirst.mockResolvedValue(null);
  mocks.mockPrisma.weightLog.findMany.mockResolvedValue([]);
  mocks.mockPrisma.syncRun.findFirst.mockResolvedValue(null);
}

describe("getTodayBundle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Freeze the entire system clock — production code uses `new Date()`
    // directly in places, not just Date.now(), so a Date.now spy alone
    // would leak real time into those calls.
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_NOW));
    setupDefaultMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe("no user", () => {
    it("returns null when no user exists", async () => {
      mocks.mockPrisma.user.findFirst.mockResolvedValue(null);
      const result = await getTodayBundle();
      expect(result).toBeNull();
    });
  });

  describe("bundle structure", () => {
    it("returns a bundle with user when user exists", async () => {
      const result = await getTodayBundle();
      expect(result).not.toBeNull();
      expect(result!.user).toEqual(MOCK_USER);
    });

    it("includes todayDate as UTC midnight", async () => {
      const result = await getTodayBundle();
      expect(result).not.toBeNull();
      const d = result!.todayDate;
      // dateOnlyUTC strips the time components, leaving midnight UTC
      expect(d.getUTCHours()).toBe(0);
      expect(d.getUTCMinutes()).toBe(0);
      expect(d.getUTCSeconds()).toBe(0);
      expect(d.getUTCMilliseconds()).toBe(0);
      // Date should be a valid Date object
      expect(d).toBeInstanceOf(Date);
      expect(isNaN(d.getTime())).toBe(false);
    });

    it("passes today's metrics to bundle", async () => {
      const mockMetrics = {
        id: "m-1",
        userId: "user-1",
        date: new Date("2024-06-15"),
        ctl: 65.0,
        atl: 70.0,
        rampRate: 1.5,
        rhr: 52,
        hrv: 45.0,
        sleepHours: 7.5,
        sleepScore: 80,
      };
      mocks.mockPrisma.dailyMetrics.findUnique.mockResolvedValueOnce(mockMetrics);
      const result = await getTodayBundle();
      expect(result!.today).toEqual(mockMetrics);
    });

    it("passes today's activities to bundle", async () => {
      const mockActivities = [
        {
          id: "a-1",
          userId: "user-1",
          date: new Date("2024-06-15"),
          type: "Run",
          durationMin: 45,
          distanceKm: 8.0,
          tss: 50,
          externalId: null,
          name: null,
          description: null,
        },
      ];
      mocks.mockPrisma.activity.findMany.mockResolvedValue(mockActivities);
      const result = await getTodayBundle();
      expect(result!.todayActivities).toEqual(mockActivities);
    });

    it("passes meal logs to bundle", async () => {
      const mockMealLogs = [
        {
          id: "ml-1",
          userId: "user-1",
          date: new Date("2024-06-15"),
          mealType: "breakfast",
          status: "hit",
          notes: null,
        },
      ];
      mocks.mockPrisma.mealLog.findMany.mockResolvedValue(mockMealLogs);
      const result = await getTodayBundle();
      expect(result!.todayMealLogs).toEqual(mockMealLogs);
    });

    it("includes latestSync in bundle", async () => {
      const finishedAt = new Date(FIXED_NOW - 30 * 60 * 1000); // 30 min ago
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.latestSync).toEqual({ finishedAt });
    });

    it("sets today and yesterday to null when no metrics", async () => {
      const result = await getTodayBundle();
      expect(result!.today).toBeNull();
      expect(result!.yesterday).toBeNull();
    });
  });

  describe("syncStatus", () => {
    it("returns stale=true and 'never synced' when no sync run", async () => {
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue(null);
      const result = await getTodayBundle();
      expect(result!.syncStatus).toEqual({
        stale: true,
        relative: "never synced",
      });
    });

    it("returns stale=false when last sync was within 6 hours", async () => {
      const finishedAt = new Date(FIXED_NOW - 2 * 60 * 60 * 1000); // 2 hours ago
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.stale).toBe(false);
    });

    it("returns stale=true when last sync was more than 6 hours ago", async () => {
      const finishedAt = new Date(FIXED_NOW - 7 * 60 * 60 * 1000); // 7 hours ago
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.stale).toBe(true);
    });

    it("returns stale=false at exactly 6h boundary (6h is not > 6h)", async () => {
      // stale = nowMs - finishedAt > SYNC_STALE_AFTER_MS
      // exactly 6h: 21600000 > 21600000 is false, so NOT stale
      const finishedAt = new Date(FIXED_NOW - 6 * 60 * 60 * 1000);
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.stale).toBe(false);
    });

    it("is stale=true at 6h + 1ms past boundary", async () => {
      const finishedAt = new Date(FIXED_NOW - 6 * 60 * 60 * 1000 - 1);
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.stale).toBe(true);
    });
  });

  describe("relativeFromNow (via syncStatus.relative)", () => {
    it("shows 'synced just now' when synced less than 30 seconds ago", async () => {
      // min = Math.round(10000/60000) = Math.round(0.167) = 0 -> "just now"
      // Note: 30s rounds to 1m (Math.round(0.5)=1), so must use < 30s
      const finishedAt = new Date(FIXED_NOW - 10 * 1000); // 10 seconds ago
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.relative).toBe("synced just now");
    });

    it("shows 'synced Nm ago' for minutes ago", async () => {
      const finishedAt = new Date(FIXED_NOW - 15 * 60 * 1000); // 15 minutes ago
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.relative).toBe("synced 15m ago");
    });

    it("shows 'synced 1m ago' at exactly 1 minute", async () => {
      const finishedAt = new Date(FIXED_NOW - 60 * 1000);
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.relative).toBe("synced 1m ago");
    });

    it("shows 'synced Nh ago' for hours ago", async () => {
      const finishedAt = new Date(FIXED_NOW - 3 * 60 * 60 * 1000); // 3 hours ago
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.relative).toBe("synced 3h ago");
    });

    it("shows 'synced Nd ago' for days ago", async () => {
      const finishedAt = new Date(FIXED_NOW - 2 * 24 * 60 * 60 * 1000); // 2 days ago
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.relative).toBe("synced 2d ago");
    });

    it("transitions from hours to days at 24h boundary", async () => {
      // h = Math.round(1440/60) = 24; 24 < 24 is false -> d = Math.round(24/24) = 1 -> "1d ago"
      const finishedAt = new Date(FIXED_NOW - 24 * 60 * 60 * 1000);
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.relative).toBe("synced 1d ago");
    });

    it("shows 'synced 59m ago' at 59 minutes", async () => {
      const finishedAt = new Date(FIXED_NOW - 59 * 60 * 1000);
      mocks.mockPrisma.syncRun.findFirst.mockResolvedValue({ finishedAt });
      const result = await getTodayBundle();
      expect(result!.syncStatus.relative).toBe("synced 59m ago");
    });
  });

  describe("latestWeightDaysAgo", () => {
    it("returns null when no latest weight", async () => {
      mocks.mockPrisma.weightLog.findFirst.mockResolvedValue(null);
      const result = await getTodayBundle();
      expect(result!.latestWeightDaysAgo).toBeNull();
    });

    it("returns 0 when weight was logged today (UTC midnight)", async () => {
      // FIXED_NOW = 2024-06-15T12:00:00Z
      // Weight date = 2024-06-15T00:00:00Z -> 12h in ms -> Math.floor(12h / 24h) = 0
      const weightDate = new Date("2024-06-15T00:00:00.000Z");
      mocks.mockPrisma.weightLog.findFirst.mockResolvedValue({
        id: "wl-1",
        userId: "user-1",
        date: weightDate,
        weightKg: 72.5,
        notes: null,
      });
      const result = await getTodayBundle();
      expect(result!.latestWeightDaysAgo).toBe(0);
    });

    it("returns 1 when weight was logged yesterday", async () => {
      // FIXED_NOW = 2024-06-15T12:00:00Z; yesterday midnight = 2024-06-14T00:00:00Z
      // diff = 36h -> Math.floor(36/24) = 1
      const weightDate = new Date("2024-06-14T00:00:00.000Z");
      mocks.mockPrisma.weightLog.findFirst.mockResolvedValue({
        id: "wl-1",
        userId: "user-1",
        date: weightDate,
        weightKg: 72.0,
        notes: null,
      });
      const result = await getTodayBundle();
      expect(result!.latestWeightDaysAgo).toBe(1);
    });

    it("returns 7 when weight was logged 7 days ago", async () => {
      const weightDate = new Date("2024-06-08T00:00:00.000Z");
      mocks.mockPrisma.weightLog.findFirst.mockResolvedValue({
        id: "wl-1",
        userId: "user-1",
        date: weightDate,
        weightKg: 73.0,
        notes: null,
      });
      const result = await getTodayBundle();
      expect(result!.latestWeightDaysAgo).toBe(7);
    });
  });

  describe("prisma query calls", () => {
    it("queries user ordered by createdAt asc", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.user.findFirst).toHaveBeenCalledWith({
        orderBy: { createdAt: "asc" },
      });
    });

    it("queries activities ordered by tss desc", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.activity.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          orderBy: { tss: "desc" },
        }),
      );
    });

    it("queries syncRun for the most recent finished run", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.syncRun.findFirst).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { finishedAt: { not: null } },
          orderBy: { finishedAt: "desc" },
          select: { finishedAt: true },
        }),
      );
    });

    it("queries dailyMetrics for both today and yesterday", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.dailyMetrics.findUnique).toHaveBeenCalledTimes(2);
    });

    it("queries all 12 data sources in parallel", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.dailyMetrics.findUnique).toHaveBeenCalledTimes(2);
      expect(mocks.mockPrisma.dailyMetrics.findMany).toHaveBeenCalledTimes(2);
      expect(mocks.mockPrisma.activity.findMany).toHaveBeenCalledOnce();
      expect(mocks.mockPrisma.activity.findFirst).toHaveBeenCalledOnce();
      expect(mocks.mockPrisma.mealLog.findMany).toHaveBeenCalledOnce();
      expect(mocks.mockPrisma.weightLog.findUnique).toHaveBeenCalledOnce();
      expect(mocks.mockPrisma.weightLog.findFirst).toHaveBeenCalledTimes(2);
      expect(mocks.mockPrisma.weightLog.findMany).toHaveBeenCalledOnce();
      expect(mocks.mockPrisma.syncRun.findFirst).toHaveBeenCalledOnce();
    });
  });

  describe("hrv7dBaseline", () => {
    it("returns null when no recent HRV data", async () => {
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValue([]);
      const result = await getTodayBundle();
      expect(result!.hrv7dBaseline).toBeNull();
    });

    it("returns null when fewer than 3 non-null HRV values", async () => {
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValue([
        { hrv: 60 },
        { hrv: null },
        { hrv: 65 },
      ]);
      const result = await getTodayBundle();
      expect(result!.hrv7dBaseline).toBeNull();
    });

    it("computes mean of ≥3 non-null HRV values", async () => {
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValue([
        { hrv: 60 },
        { hrv: 65 },
        { hrv: 70 },
        { hrv: null },
      ]);
      const result = await getTodayBundle();
      expect(result!.hrv7dBaseline).toBeCloseTo(65, 5);
    });
  });

  describe("daysSinceLastActivity", () => {
    it("returns null when no activities exist", async () => {
      mocks.mockPrisma.activity.findFirst.mockResolvedValue(null);
      const result = await getTodayBundle();
      expect(result!.daysSinceLastActivity).toBeNull();
    });

    it("returns 0 when most recent activity was today (UTC midnight)", async () => {
      // FIXED_NOW = 2024-06-15T12:00:00Z; today UTC midnight = 2024-06-15T00:00:00Z
      mocks.mockPrisma.activity.findFirst.mockResolvedValue({
        date: new Date("2024-06-15T00:00:00.000Z"),
      });
      const result = await getTodayBundle();
      expect(result!.daysSinceLastActivity).toBe(0);
    });

    it("returns 3 when most recent activity was 3 days ago", async () => {
      mocks.mockPrisma.activity.findFirst.mockResolvedValue({
        date: new Date("2024-06-12T00:00:00.000Z"),
      });
      const result = await getTodayBundle();
      expect(result!.daysSinceLastActivity).toBe(3);
    });

    it("returns 1 when most recent activity was 1 day ago", async () => {
      mocks.mockPrisma.activity.findFirst.mockResolvedValue({
        date: new Date("2024-06-14T00:00:00.000Z"),
      });
      const result = await getTodayBundle();
      expect(result!.daysSinceLastActivity).toBe(1);
    });

    it("returns 0 (not negative) when activity date is in the future", () => {
      // Math.max(0, ...) clamps negatives to 0
      mocks.mockPrisma.activity.findFirst.mockResolvedValue({
        date: new Date("2024-06-20T00:00:00.000Z"), // 5 days ahead of FIXED_NOW
      });
      return getTodayBundle().then((result) => {
        expect(result!.daysSinceLastActivity).toBe(0);
      });
    });
  });

  describe("hrv7dBaseline: additional edge cases", () => {
    it("computes baseline with exactly 3 non-null values (minimum valid)", async () => {
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValue([
        { hrv: 60 },
        { hrv: 66 },
        { hrv: 72 },
      ]);
      const result = await getTodayBundle();
      expect(result!.hrv7dBaseline).toBeCloseTo(66, 5);
    });

    it("computes correct mean for all 7 non-null values", async () => {
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValue([
        { hrv: 60 },
        { hrv: 62 },
        { hrv: 64 },
        { hrv: 66 },
        { hrv: 68 },
        { hrv: 70 },
        { hrv: 72 },
      ]);
      const result = await getTodayBundle();
      // Mean = (60+62+64+66+68+70+72) / 7 = 462 / 7 = 66
      expect(result!.hrv7dBaseline).toBeCloseTo(66, 5);
    });

    it("returns null for exactly 2 non-null HRV values (below minimum)", async () => {
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValue([
        { hrv: 60 },
        { hrv: null },
        { hrv: null },
        { hrv: null },
        { hrv: 70 },
      ]);
      const result = await getTodayBundle();
      expect(result!.hrv7dBaseline).toBeNull();
    });
  });

  describe("new query parameters", () => {
    it("queries activity.findFirst ordered by date descending to get most recent activity", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.activity.findFirst).toHaveBeenCalledWith(
        expect.objectContaining({
          orderBy: { date: "desc" },
          select: { date: true },
        }),
      );
    });

    it("queries dailyMetrics.findMany with take: 7 for HRV baseline", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.dailyMetrics.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          select: { hrv: true },
          orderBy: { date: "desc" },
          take: 7,
        }),
      );
    });

    it("queries dailyMetrics.findMany with take: 14 for sparklines", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.dailyMetrics.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: {
            userId: "user-1",
            date: {
              gte: new Date("2024-06-02T00:00:00.000Z"),
              lte: new Date("2024-06-15T00:00:00.000Z"),
            },
          },
          orderBy: { date: "desc" },
          take: 14,
        }),
      );
    });

    it("queries weightLog.findMany with take: 14 for sparklines", async () => {
      await getTodayBundle();
      expect(mocks.mockPrisma.weightLog.findMany).toHaveBeenCalledWith(
        expect.objectContaining({
          where: {
            userId: "user-1",
            date: {
              gte: new Date("2024-06-02T00:00:00.000Z"),
              lte: new Date("2024-06-15T00:00:00.000Z"),
            },
          },
          orderBy: { date: "desc" },
          take: 14,
        }),
      );
    });
  });

  describe("sparkline data", () => {
    it("includes dailyMetrics14d as empty array when no rows", async () => {
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValue([]);
      const result = await getTodayBundle();
      expect(result!.dailyMetrics14d).toEqual([]);
    });

    it("returns dailyMetrics14d in ascending date order (reversed from desc query)", async () => {
      const rows = [
        { id: "m3", userId: "user-1", date: new Date("2024-06-15"), ctl: 70, atl: 75, rampRate: 2, rhr: 52, hrv: 48, sleepHours: 7, sleepScore: 80, steps: null, kcalConsumed: null, carbsGrams: null, proteinGrams: null, fatGrams: null },
        { id: "m2", userId: "user-1", date: new Date("2024-06-14"), ctl: 68, atl: 73, rampRate: 2, rhr: 53, hrv: 46, sleepHours: 7, sleepScore: 78, steps: null, kcalConsumed: null, carbsGrams: null, proteinGrams: null, fatGrams: null },
        { id: "m1", userId: "user-1", date: new Date("2024-06-13"), ctl: 66, atl: 71, rampRate: 2, rhr: 54, hrv: 44, sleepHours: 6.5, sleepScore: 75, steps: null, kcalConsumed: null, carbsGrams: null, proteinGrams: null, fatGrams: null },
      ];
      // Simulate desc query result
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValueOnce([]);
      mocks.mockPrisma.dailyMetrics.findMany.mockResolvedValueOnce([rows[0], rows[1], rows[2]]);
      const result = await getTodayBundle();
      // Should be reversed to ascending
      expect(result!.dailyMetrics14d[0].date).toEqual(new Date("2024-06-13"));
      expect(result!.dailyMetrics14d[2].date).toEqual(new Date("2024-06-15"));
    });

    it("includes weightLogs14d as empty array when no rows", async () => {
      mocks.mockPrisma.weightLog.findMany.mockResolvedValue([]);
      const result = await getTodayBundle();
      expect(result!.weightLogs14d).toEqual([]);
    });

    it("returns weightLogs14d in ascending date order (reversed from desc query)", async () => {
      const logs = [
        { id: "w3", userId: "user-1", date: new Date("2024-06-15"), weightKg: 72.0, notes: null },
        { id: "w2", userId: "user-1", date: new Date("2024-06-14"), weightKg: 72.3, notes: null },
        { id: "w1", userId: "user-1", date: new Date("2024-06-13"), weightKg: 72.6, notes: null },
      ];
      mocks.mockPrisma.weightLog.findMany.mockResolvedValue([logs[0], logs[1], logs[2]]);
      const result = await getTodayBundle();
      expect(result!.weightLogs14d[0].date).toEqual(new Date("2024-06-13"));
      expect(result!.weightLogs14d[2].date).toEqual(new Date("2024-06-15"));
    });
  });
});
