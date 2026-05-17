import { describe, it, expect } from "vitest";
import { computeCoachDecision, buildCoachInput } from "../rules";
import type { CoachInput } from "../rules";
import type { TodayBundle } from "@/lib/queries/today";

function makeInput(overrides: Partial<CoachInput> = {}): CoachInput {
  return {
    rampRate: null,
    hrv: null,
    rhr: null,
    baselineRhr: null,
    sleepHours: null,
    sleepScore: null,
    yesterdayHrv: null,
    ...overrides,
  };
}

describe("computeCoachDecision", () => {
  describe("missing-data", () => {
    it("returns missing-data when all key metrics are null", () => {
      const decision = computeCoachDecision(makeInput());
      expect(decision.category).toBe("missing-data");
      expect(decision.dataQuality).toBe("insufficient");
    });

    it("returns missing-data when only hrv is present (no ramp/sleep)", () => {
      const decision = computeCoachDecision(makeInput({ hrv: 65 }));
      expect(decision.category).toBe("missing-data");
    });
  });

  describe("data quality", () => {
    it("is sufficient when ramp rate and sleep are both present", () => {
      const decision = computeCoachDecision(makeInput({ rampRate: 2, sleepHours: 7.5 }));
      expect(decision.dataQuality).toBe("sufficient");
    });

    it("is partial when sleep is present but ramp rate is missing", () => {
      const decision = computeCoachDecision(makeInput({ sleepHours: 7 }));
      expect(decision.dataQuality).toBe("partial");
    });

    it("is partial when ramp rate is present but sleep is missing", () => {
      const decision = computeCoachDecision(makeInput({ rampRate: 2 }));
      expect(decision.dataQuality).toBe("partial");
    });

    it("is sufficient when sleep score substitutes for sleep hours", () => {
      const decision = computeCoachDecision(makeInput({ rampRate: 3, sleepScore: 75 }));
      expect(decision.dataQuality).toBe("sufficient");
    });
  });

  describe("recovery", () => {
    it("recommends full recovery for very high ramp rate", () => {
      // rampRate > 8: +4 → score 4 → recovery
      const decision = computeCoachDecision(makeInput({ rampRate: 9, sleepHours: 7 }));
      expect(decision.category).toBe("recovery");
    });

    it("recommends full recovery for very short sleep combined with high ramp", () => {
      // rampRate > 5: +2, sleepHours < 5.5: +4 → score 6 → recovery
      const decision = computeCoachDecision(makeInput({ rampRate: 6, sleepHours: 5 }));
      expect(decision.category).toBe("recovery");
    });

    it("recommends recovery for very short sleep alone", () => {
      // sleepHours < 5.5: +4 → score 4 → recovery
      const decision = computeCoachDecision(makeInput({ rampRate: 2, sleepHours: 4.5 }));
      expect(decision.category).toBe("recovery");
    });
  });

  describe("controlled-recovery", () => {
    it("recommends controlled recovery for high ramp rate (5–8) with good sleep", () => {
      // rampRate > 5: +2 → score 2 → controlled-recovery
      const decision = computeCoachDecision(makeInput({ rampRate: 6, sleepHours: 7.5 }));
      expect(decision.category).toBe("controlled-recovery");
    });

    it("recommends controlled recovery for moderate ramp with poor sleep", () => {
      // rampRate > 3: +1, sleepHours < 6.5: +2 → score 3 → controlled-recovery
      const decision = computeCoachDecision(makeInput({ rampRate: 4, sleepHours: 6 }));
      expect(decision.category).toBe("controlled-recovery");
    });

    it("includes ramp rate reason in why", () => {
      const decision = computeCoachDecision(makeInput({ rampRate: 6, sleepHours: 7.5 }));
      expect(decision.why.some((r) => r.toLowerCase().includes("ramp"))).toBe(true);
    });
  });

  describe("caution", () => {
    it("recommends caution for mild ramp with decent sleep", () => {
      // rampRate > 3: +1, sleepHours 7.5 → no signal → score 1 → caution
      const decision = computeCoachDecision(makeInput({ rampRate: 4, sleepHours: 7.5 }));
      expect(decision.category).toBe("caution");
    });

    it("recommends caution for slightly short sleep", () => {
      // sleepHours < 7: +1 → score 1 → caution
      const decision = computeCoachDecision(makeInput({ rampRate: 2, sleepHours: 6.8 }));
      expect(decision.category).toBe("caution");
    });

    it("recommends caution for elevated RHR above baseline", () => {
      // rhr delta 6 > 4: +1, rampRate 2 no signal, sleepHours 7.5 no signal → score 1 → caution
      const decision = computeCoachDecision(
        makeInput({ rampRate: 2, sleepHours: 7.5, rhr: 60, baselineRhr: 54 }),
      );
      expect(decision.category).toBe("caution");
    });

    it("ignores RHR signal when baseline is missing", () => {
      // No baselineRhr → no RHR signal → score 0 → steady
      const decision = computeCoachDecision(
        makeInput({ rampRate: 2, sleepHours: 7.5, rhr: 75 }),
      );
      expect(decision.category).toBe("steady");
    });
  });

  describe("steady", () => {
    it("recommends steady for normal metrics", () => {
      const decision = computeCoachDecision(
        makeInput({ rampRate: 2, sleepHours: 7.5, sleepScore: 80 }),
      );
      expect(decision.category).toBe("steady");
    });

    it("recommends steady for low ramp, good sleep, and normal RHR", () => {
      const decision = computeCoachDecision(
        makeInput({ rampRate: 1, sleepHours: 8, rhr: 50, baselineRhr: 51 }),
      );
      expect(decision.category).toBe("steady");
    });

    it("includes fallback why message when no signals fired", () => {
      const decision = computeCoachDecision(makeInput({ rampRate: 1, sleepHours: 8 }));
      expect(decision.why.length).toBeGreaterThan(0);
      expect(decision.why[0]).toBe("All metrics look normal.");
    });
  });

  describe("HRV suppression signals", () => {
    it("adds score for significant HRV suppression vs yesterday", () => {
      // hrv 45 / yesterdayHrv 65 = 0.69 < 0.75 → +2 → controlled-recovery
      const decision = computeCoachDecision(
        makeInput({ rampRate: 2, sleepHours: 7, hrv: 45, yesterdayHrv: 65 }),
      );
      expect(["caution", "controlled-recovery"]).toContain(decision.category);
    });

    it("ignores HRV signal when yesterdayHrv is null", () => {
      const withoutYesterday = computeCoachDecision(
        makeInput({ rampRate: 2, sleepHours: 7.5, hrv: 45 }),
      );
      const withNullYesterday = computeCoachDecision(
        makeInput({ rampRate: 2, sleepHours: 7.5, hrv: 45, yesterdayHrv: null }),
      );
      expect(withoutYesterday.category).toBe(withNullYesterday.category);
    });

    it("ignores HRV signal when current hrv is null", () => {
      const decision = computeCoachDecision(
        makeInput({ rampRate: 2, sleepHours: 7.5, hrv: null, yesterdayHrv: 65 }),
      );
      expect(decision.category).toBe("steady");
    });
  });

  describe("output shape", () => {
    it("always has title, doItems, and watch across all categories", () => {
      const cases: CoachInput[] = [
        makeInput(),
        makeInput({ rampRate: 9, sleepHours: 5 }),
        makeInput({ rampRate: 6, sleepHours: 7.5 }),
        makeInput({ rampRate: 4, sleepHours: 7.5 }),
        makeInput({ rampRate: 2, sleepHours: 7.5 }),
      ];
      for (const input of cases) {
        const decision = computeCoachDecision(input);
        expect(decision.title).toBeTruthy();
        expect(decision.doItems.length).toBeGreaterThan(0);
        expect(typeof decision.watch).toBe("string");
        expect(decision.watch.length).toBeGreaterThan(0);
      }
    });
  });
});

describe("buildCoachInput", () => {
  it("maps bundle fields correctly", () => {
    const bundle = {
      user: { baselineRhr: 55 },
      today: {
        rampRate: 4.5,
        hrv: 65,
        rhr: 58,
        sleepHours: 7.2,
        sleepScore: 72,
      },
      yesterday: { hrv: 70 },
    } as unknown as TodayBundle;

    const input = buildCoachInput(bundle);
    expect(input.rampRate).toBe(4.5);
    expect(input.hrv).toBe(65);
    expect(input.rhr).toBe(58);
    expect(input.baselineRhr).toBe(55);
    expect(input.sleepHours).toBe(7.2);
    expect(input.sleepScore).toBe(72);
    expect(input.yesterdayHrv).toBe(70);
  });

  it("handles null today gracefully", () => {
    const bundle = {
      user: { baselineRhr: null },
      today: null,
      yesterday: null,
    } as unknown as TodayBundle;

    const input = buildCoachInput(bundle);
    expect(input.rampRate).toBeNull();
    expect(input.hrv).toBeNull();
    expect(input.rhr).toBeNull();
    expect(input.baselineRhr).toBeNull();
    expect(input.sleepHours).toBeNull();
    expect(input.yesterdayHrv).toBeNull();
  });

  it("handles null yesterday gracefully", () => {
    const bundle = {
      user: { baselineRhr: 52 },
      today: { rampRate: 3, hrv: 60, rhr: 55, sleepHours: 7, sleepScore: 70 },
      yesterday: null,
    } as unknown as TodayBundle;

    const input = buildCoachInput(bundle);
    expect(input.yesterdayHrv).toBeNull();
    expect(input.rampRate).toBe(3);
  });
});
