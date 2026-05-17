import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TodayHero } from "../TodayHero";
import type { TodayBundle } from "@/lib/queries/today";

// Minimal bundle helper — fields not needed for a given test can be omitted;
// the component casts through buildCoachInput which handles nulls safely.
function makeBundle(overrides: Partial<TodayBundle> = {}): TodayBundle {
  return {
    user: { baselineRhr: null } as TodayBundle["user"],
    today: null,
    yesterday: null,
    todayActivities: [],
    todayMealLogs: [],
    todayWeight: null,
    latestWeight: null,
    weightWeekAgo: null,
    latestSync: null,
    syncStatus: { stale: true, relative: "never synced" },
    latestWeightDaysAgo: null,
    todayDate: new Date("2024-06-15T00:00:00.000Z"),
    hrv7dBaseline: null,
    daysSinceLastActivity: null,
    ...overrides,
  };
}

// A bundle with all primary data present → steady recommendation, high confidence
function makeFreshBundle(): TodayBundle {
  return makeBundle({
    today: {
      id: "m-1",
      userId: "user-1",
      date: new Date("2024-06-15"),
      rampRate: 2,
      hrv: 65,
      rhr: 52,
      sleepHours: 7.5,
      sleepScore: 80,
      ctl: 55,
      atl: 57,
      steps: null,
      kcalConsumed: null,
      carbsGrams: null,
      proteinGrams: null,
      fatGrams: null,
    } as TodayBundle["today"],
    latestSync: { finishedAt: new Date() }, // synced just now
    hrv7dBaseline: 63,
    todayWeight: { id: "w-1", userId: "user-1", date: new Date("2024-06-15"), weightKg: 72, notes: null },
    daysSinceLastActivity: 1,
    latestWeightDaysAgo: 0,
  });
}

describe("TodayHero", () => {
  describe("card heading", () => {
    it("renders the decision title", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      expect(screen.getByText("Good day for steady training.")).toBeInTheDocument();
    });
  });

  describe("confidence display", () => {
    it("shows the confidence percentage as text", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      // With all data present, confidence should be 100.
      expect(screen.getByText("100% confidence")).toBeInTheDocument();
    });

    it("confidence span has a descriptive aria-label", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      expect(screen.getByLabelText("Data confidence: 100%")).toBeInTheDocument();
    });

    it("shows 35% confidence when today metrics are missing but other data is present", () => {
      // today=null → -65. hrv7dBaseline present = no penalty. weight present = no penalty.
      // latestSync fresh = syncStaleDays 0 → no penalty. Total = 100 - 65 = 35
      const bundle = makeBundle({
        latestSync: { finishedAt: new Date() },
        hrv7dBaseline: 60,
        todayWeight: { id: "w-1", userId: "user-1", date: new Date(), weightKg: 72, notes: null },
        daysSinceLastActivity: 1,
        latestWeightDaysAgo: 0,
      });
      render(<TodayHero bundle={bundle} />);
      expect(screen.getByText("35% confidence")).toBeInTheDocument();
    });

    it("confidence span title matches the percentage shown", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      const span = screen.getByLabelText("Data confidence: 100%");
      expect(span).toHaveAttribute("title", "Data confidence: 100%");
    });
  });

  describe("category badge", () => {
    it("shows 'needs data' badge when no metrics available", () => {
      render(<TodayHero bundle={makeBundle()} />);
      expect(screen.getByText("needs data")).toBeInTheDocument();
    });

    it("shows 'steady' badge for normal healthy metrics", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      expect(screen.getByText("steady")).toBeInTheDocument();
    });

    it("shows 'recovery' badge for very high ramp rate", () => {
      const bundle = makeFreshBundle();
      (bundle.today as NonNullable<TodayBundle["today"]>).rampRate = 9;
      render(<TodayHero bundle={bundle} />);
      expect(screen.getByText("recovery")).toBeInTheDocument();
    });

    it("shows 'controlled recovery' badge for elevated ramp rate", () => {
      const bundle = makeFreshBundle();
      (bundle.today as NonNullable<TodayBundle["today"]>).rampRate = 6;
      render(<TodayHero bundle={bundle} />);
      expect(screen.getByText("controlled recovery")).toBeInTheDocument();
    });
  });

  describe("freshness warnings", () => {
    it("does not render a freshness list when there are no warnings", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      // No source labels should appear
      expect(screen.queryByText("Wellness:")).not.toBeInTheDocument();
      expect(screen.queryByText("Activity:")).not.toBeInTheDocument();
      expect(screen.queryByText("Weight:")).not.toBeInTheDocument();
    });

    it("shows 'Wellness:' label when wellness data is missing (no today metrics)", () => {
      // hasTodayMetrics = false → wellness missing warning
      const bundle = makeBundle({ daysSinceLastActivity: 1 });
      render(<TodayHero bundle={bundle} />);
      expect(screen.getByText("Wellness:")).toBeInTheDocument();
    });

    it("shows the wellness warning message when wellness data not synced", () => {
      const bundle = makeBundle({ daysSinceLastActivity: 1 });
      render(<TodayHero bundle={bundle} />);
      expect(screen.getAllByText("Wellness data not synced today.")).toHaveLength(2);
    });

    it("shows 'Activity:' label when last activity was stale (4+ days ago)", () => {
      const bundle = makeFreshBundle();
      bundle.daysSinceLastActivity = 5;
      render(<TodayHero bundle={bundle} />);
      expect(screen.getByText("Activity:")).toBeInTheDocument();
    });

    it("shows 'Weight:' label when weight not logged today and old (>3 days)", () => {
      const bundle = makeFreshBundle();
      bundle.todayWeight = null;
      bundle.latestWeightDaysAgo = 5;
      render(<TodayHero bundle={bundle} />);
      expect(screen.getByText("Weight:")).toBeInTheDocument();
    });

    it("shows multiple source labels when multiple sources are stale", () => {
      // No today metrics = wellness missing; stale activity; stale weight
      const bundle = makeBundle({
        daysSinceLastActivity: 5,
        latestWeightDaysAgo: 4,
      });
      render(<TodayHero bundle={bundle} />);
      expect(screen.getByText("Wellness:")).toBeInTheDocument();
      expect(screen.getByText("Activity:")).toBeInTheDocument();
      expect(screen.getByText("Weight:")).toBeInTheDocument();
    });
  });

  describe("recommendation content", () => {
    it("renders a non-empty decision title inside the card", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      // The decision title is rendered in the hero heading.
      // For a steady/normal bundle the title is defined in COACH_TITLES["steady"]
      const card = screen.getByText("Good day for steady training.").closest("div");
      expect(card).toBeTruthy();
    });

    it("renders the 'Why' section heading", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      expect(screen.getByText("Why")).toBeInTheDocument();
    });

    it("renders the 'What to do' section heading", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      expect(screen.getByText("What to do")).toBeInTheDocument();
    });

    it("renders the 'Watch for' section heading", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      expect(screen.getByText("Watch for")).toBeInTheDocument();
    });
  });

  describe("confidence color classes", () => {
    it("applies emerald color class when confidence >= 85 (full bundle, 100%)", () => {
      render(<TodayHero bundle={makeFreshBundle()} />);
      const confidenceEl = screen.getByLabelText("Data confidence: 100%");
      expect(confidenceEl.className).toContain("text-emerald-600");
    });

    it("applies rose color class when confidence < 40 (35% — no today metrics)", () => {
      // today=null → -65 penalty only (other data present, fresh sync) → 35% → < 40 → rose
      const bundle = makeBundle({
        latestSync: { finishedAt: new Date() },
        hrv7dBaseline: 60,
        todayWeight: { id: "w-1", userId: "user-1", date: new Date(), weightKg: 72, notes: null },
        daysSinceLastActivity: 1,
        latestWeightDaysAgo: 0,
      });
      render(<TodayHero bundle={bundle} />);
      const confidenceEl = screen.getByLabelText("Data confidence: 35%");
      expect(confidenceEl.className).toContain("text-rose-600");
    });
  });
});