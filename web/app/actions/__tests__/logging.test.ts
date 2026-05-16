import { describe, it, expect, vi, beforeEach } from "vitest";

const mocks = vi.hoisted(() => {
  const mockCookiesGet = vi.fn();
  const mockCookies = vi.fn(() =>
    Promise.resolve({ get: mockCookiesGet }),
  );
  const mockRevalidatePath = vi.fn();
  const mockRedirect = vi.fn(() => {
    throw new Error("NEXT_REDIRECT");
  });
  const mockPrisma = {
    user: { findFirst: vi.fn() },
    weightLog: { upsert: vi.fn() },
    mealLog: { upsert: vi.fn() },
  };
  const mockVerifySession = vi.fn();
  return {
    mockCookiesGet,
    mockCookies,
    mockRevalidatePath,
    mockRedirect,
    mockPrisma,
    mockVerifySession,
  };
});

vi.mock("next/headers", () => ({
  cookies: mocks.mockCookies,
}));

vi.mock("next/cache", () => ({
  revalidatePath: mocks.mockRevalidatePath,
}));

vi.mock("next/navigation", () => ({
  redirect: mocks.mockRedirect,
}));

vi.mock("@/lib/db", () => ({
  prisma: mocks.mockPrisma,
}));

vi.mock("@/lib/auth", () => ({
  COOKIE_NAME: "dashboard_session",
  verifySession: mocks.mockVerifySession,
}));

import { logWeight, logMeal } from "../logging";

const MOCK_USER = {
  id: "user-1",
  email: "test@example.com",
  createdAt: new Date("2024-01-01"),
  updatedAt: new Date("2024-01-01"),
  targetWeight: null,
  targetDate: null,
  baselineRhr: null,
};

function makeFormData(fields: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) {
    fd.append(k, v);
  }
  return fd;
}

describe("logWeight", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.mockCookiesGet.mockReturnValue({ value: "valid-cookie" });
    mocks.mockVerifySession.mockReturnValue(true);
    mocks.mockPrisma.user.findFirst.mockResolvedValue(MOCK_USER);
    mocks.mockPrisma.weightLog.upsert.mockResolvedValue({});
  });

  describe("input validation", () => {
    it("returns error when weightKg is missing", async () => {
      const result = await logWeight(null, makeFormData({}));
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toBeTruthy();
      }
    });

    it("returns error when weightKg is below 30", async () => {
      const result = await logWeight(null, makeFormData({ weightKg: "25" }));
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toContain("30 kg");
      }
    });

    it("returns error when weightKg is above 250", async () => {
      const result = await logWeight(null, makeFormData({ weightKg: "300" }));
      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error).toContain("250 kg");
      }
    });

    it("returns error when weightKg is not a number", async () => {
      const result = await logWeight(
        null,
        makeFormData({ weightKg: "not-a-number" }),
      );
      expect(result.ok).toBe(false);
    });

    it("accepts minimum valid weight of 30", async () => {
      const result = await logWeight(null, makeFormData({ weightKg: "30" }));
      expect(result.ok).toBe(true);
    });

    it("accepts maximum valid weight of 250", async () => {
      const result = await logWeight(null, makeFormData({ weightKg: "250" }));
      expect(result.ok).toBe(true);
    });

    it("accepts valid weight in normal range", async () => {
      const result = await logWeight(null, makeFormData({ weightKg: "72.5" }));
      expect(result.ok).toBe(true);
    });

    it("rounds weight to 1 decimal place on upsert", async () => {
      await logWeight(null, makeFormData({ weightKg: "72.55" }));
      const upsertCall = mocks.mockPrisma.weightLog.upsert.mock.calls[0][0];
      // 72.55 * 10 = 725.5 -> round -> 726 -> /10 = 72.6
      expect(upsertCall.update.weightKg).toBeCloseTo(72.6, 5);
    });

    it("does not call prisma when validation fails", async () => {
      await logWeight(null, makeFormData({ weightKg: "5" }));
      expect(mocks.mockPrisma.weightLog.upsert).not.toHaveBeenCalled();
    });
  });

  describe("authentication", () => {
    it("redirects to /login when session is invalid", async () => {
      mocks.mockVerifySession.mockReturnValue(false);
      await expect(
        logWeight(null, makeFormData({ weightKg: "72" })),
      ).rejects.toThrow("NEXT_REDIRECT");
      expect(mocks.mockRedirect).toHaveBeenCalledWith("/login");
    });

    it("throws when no user is found in DB", async () => {
      mocks.mockPrisma.user.findFirst.mockResolvedValue(null);
      await expect(
        logWeight(null, makeFormData({ weightKg: "72" })),
      ).rejects.toThrow("No user seeded");
    });
  });

  describe("success path", () => {
    it("calls prisma.weightLog.upsert with correct userId", async () => {
      await logWeight(null, makeFormData({ weightKg: "72.5" }));
      expect(mocks.mockPrisma.weightLog.upsert).toHaveBeenCalledOnce();
      const call = mocks.mockPrisma.weightLog.upsert.mock.calls[0][0];
      expect(call.where.userId_date.userId).toBe("user-1");
    });

    it("sets notes to null on update (protects manual entry from sync)", async () => {
      await logWeight(null, makeFormData({ weightKg: "72.5" }));
      const call = mocks.mockPrisma.weightLog.upsert.mock.calls[0][0];
      expect(call.update.notes).toBeNull();
    });

    it("calls revalidatePath('/') after successful upsert", async () => {
      await logWeight(null, makeFormData({ weightKg: "72.5" }));
      expect(mocks.mockRevalidatePath).toHaveBeenCalledWith("/");
    });

    it("returns {ok: true} on success", async () => {
      const result = await logWeight(null, makeFormData({ weightKg: "72.5" }));
      expect(result).toEqual({ ok: true });
    });

    it("create payload includes weightKg without notes field", async () => {
      await logWeight(null, makeFormData({ weightKg: "75.0" }));
      const call = mocks.mockPrisma.weightLog.upsert.mock.calls[0][0];
      expect(call.create.weightKg).toBe(75.0);
      expect(call.create).not.toHaveProperty("notes");
    });
  });
});

describe("logMeal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.mockCookiesGet.mockReturnValue({ value: "valid-cookie" });
    mocks.mockVerifySession.mockReturnValue(true);
    mocks.mockPrisma.user.findFirst.mockResolvedValue(MOCK_USER);
    mocks.mockPrisma.mealLog.upsert.mockResolvedValue({});
  });

  describe("input validation", () => {
    it("returns error for invalid mealType", async () => {
      // @ts-expect-error - testing runtime validation of invalid meal type
      const result = await logMeal("invalid", "hit");
      expect(result.ok).toBe(false);
    });

    it("returns error for invalid status", async () => {
      // @ts-expect-error - testing runtime validation of invalid status
      const result = await logMeal("breakfast", "invalid");
      expect(result.ok).toBe(false);
    });

    it("accepts all valid meal types", async () => {
      const types = ["breakfast", "comida", "merienda", "cena"] as const;
      for (const type of types) {
        vi.clearAllMocks();
        mocks.mockCookiesGet.mockReturnValue({ value: "valid-cookie" });
        mocks.mockVerifySession.mockReturnValue(true);
        mocks.mockPrisma.user.findFirst.mockResolvedValue(MOCK_USER);
        mocks.mockPrisma.mealLog.upsert.mockResolvedValue({});

        const result = await logMeal(type, "hit");
        expect(result.ok).toBe(true);
      }
    });

    it("accepts all valid meal statuses", async () => {
      const statuses = ["hit", "partial", "missed"] as const;
      for (const status of statuses) {
        vi.clearAllMocks();
        mocks.mockCookiesGet.mockReturnValue({ value: "valid-cookie" });
        mocks.mockVerifySession.mockReturnValue(true);
        mocks.mockPrisma.user.findFirst.mockResolvedValue(MOCK_USER);
        mocks.mockPrisma.mealLog.upsert.mockResolvedValue({});

        const result = await logMeal("breakfast", status);
        expect(result.ok).toBe(true);
      }
    });

    it("does not call prisma when validation fails", async () => {
      // @ts-expect-error - testing runtime validation of invalid status
      await logMeal("breakfast", "invalid");
      expect(mocks.mockPrisma.mealLog.upsert).not.toHaveBeenCalled();
    });
  });

  describe("authentication", () => {
    it("redirects to /login when session is invalid", async () => {
      mocks.mockVerifySession.mockReturnValue(false);
      await expect(logMeal("breakfast", "hit")).rejects.toThrow(
        "NEXT_REDIRECT",
      );
      expect(mocks.mockRedirect).toHaveBeenCalledWith("/login");
    });

    it("throws when no user is found in DB", async () => {
      mocks.mockPrisma.user.findFirst.mockResolvedValue(null);
      await expect(logMeal("breakfast", "hit")).rejects.toThrow(
        "No user seeded",
      );
    });
  });

  describe("success path", () => {
    it("calls prisma.mealLog.upsert with correct mealType", async () => {
      await logMeal("comida", "partial");
      expect(mocks.mockPrisma.mealLog.upsert).toHaveBeenCalledOnce();
      const call = mocks.mockPrisma.mealLog.upsert.mock.calls[0][0];
      expect(call.create.mealType).toBe("comida");
      expect(call.create.status).toBe("partial");
    });

    it("calls prisma.mealLog.upsert with correct userId", async () => {
      await logMeal("breakfast", "hit");
      const call = mocks.mockPrisma.mealLog.upsert.mock.calls[0][0];
      expect(call.create.userId).toBe("user-1");
    });

    it("calls revalidatePath('/') after successful upsert", async () => {
      await logMeal("breakfast", "hit");
      expect(mocks.mockRevalidatePath).toHaveBeenCalledWith("/");
    });

    it("returns {ok: true} on success", async () => {
      const result = await logMeal("breakfast", "hit");
      expect(result).toEqual({ ok: true });
    });

    it("upsert where clause includes mealType for uniqueness", async () => {
      await logMeal("merienda", "missed");
      const call = mocks.mockPrisma.mealLog.upsert.mock.calls[0][0];
      expect(call.where.userId_date_mealType.mealType).toBe("merienda");
    });

    it("upsert update only sets status field", async () => {
      await logMeal("cena", "hit");
      const call = mocks.mockPrisma.mealLog.upsert.mock.calls[0][0];
      expect(call.update).toEqual({ status: "hit" });
    });
  });
});