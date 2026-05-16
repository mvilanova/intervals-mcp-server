import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const mocks = vi.hoisted(() => {
  const mockPrisma = {
    user: { findFirst: vi.fn() },
    dailyMetrics: { findUnique: vi.fn() },
    activity: { findMany: vi.fn() },
    mealLog: { findMany: vi.fn() },
    weightLog: {
      findUnique: vi.fn(),
      findFirst: vi.fn(),
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
  mocks.mockPrisma.activity.findMany.mockResolvedValue([]);
  mocks.mockPrisma.mealLog.findMany.mockResolvedValue([]);
  mocks.mockPrisma.weightLog.findUnique.mockResolvedValue(null);
  mocks.mockPrisma.weightLog.findFirst.mockResolvedValue(null);
  mocks.mockPrisma.syncRun.findFirst.mockResolvedValue(null);
}

describe("getTodayBundle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(Date, "now").mockReturnValue(FIXED_NOW);
    setupDefaultMocks();
  });

  afterEach(() => {
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

    it("queries all 8 data sources in parallel", async () => {
      await getTodayBundle();
      // Verify all queries were made
      expect(mocks.mockPrisma.dailyMetrics.findUnique).toHaveBeenCalledTimes(2);
      expect(mocks.mockPrisma.activity.findMany).toHaveBeenCalledOnce();
      expect(mocks.mockPrisma.mealLog.findMany).toHaveBeenCalledOnce();
      expect(mocks.mockPrisma.weightLog.findUnique).toHaveBeenCalledOnce();
      expect(mocks.mockPrisma.weightLog.findFirst).toHaveBeenCalledTimes(2);
      expect(mocks.mockPrisma.syncRun.findFirst).toHaveBeenCalledOnce();
    });
  });
});