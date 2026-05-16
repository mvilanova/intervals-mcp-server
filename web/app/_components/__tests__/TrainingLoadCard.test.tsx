import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrainingLoadCard } from "../TrainingLoadCard";
import type { DailyMetrics } from "@prisma/client";

function makeMetrics(overrides: Partial<DailyMetrics> = {}): DailyMetrics {
  return {
    id: "metrics-1",
    userId: "user-1",
    date: new Date("2024-01-15"),
    ctl: null,
    atl: null,
    rampRate: null,
    rhr: null,
    hrv: null,
    sleepHours: null,
    sleepScore: null,
    steps: null,
    kcalConsumed: null,
    carbsGrams: null,
    proteinGrams: null,
    fatGrams: null,
    ...overrides,
  };
}

describe("TrainingLoadCard", () => {
  it("renders section heading", () => {
    render(<TrainingLoadCard today={null} yesterday={null} />);
    expect(screen.getByText("Training load")).toBeInTheDocument();
  });

  it("renders metric labels CTL, ATL, Ramp", () => {
    render(<TrainingLoadCard today={null} yesterday={null} />);
    expect(screen.getByText("CTL")).toBeInTheDocument();
    expect(screen.getByText("ATL")).toBeInTheDocument();
    expect(screen.getByText("Ramp")).toBeInTheDocument();
  });

  describe("null values", () => {
    it("shows em-dashes for all metrics when today is null", () => {
      render(<TrainingLoadCard today={null} yesterday={null} />);
      const dashes = screen.getAllByText("—");
      expect(dashes).toHaveLength(3);
    });

    it("shows em-dashes when CTL and ATL are null", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: null, atl: null, rampRate: null })}
          yesterday={null}
        />,
      );
      const dashes = screen.getAllByText("—");
      expect(dashes).toHaveLength(3);
    });
  });

  describe("fmt function", () => {
    it("shows CTL with 1 decimal place", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: 65.3 })}
          yesterday={null}
        />,
      );
      expect(screen.getByText("65.3")).toBeInTheDocument();
    });

    it("shows ATL with 1 decimal place", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ atl: 72.0 })}
          yesterday={null}
        />,
      );
      expect(screen.getByText("72.0")).toBeInTheDocument();
    });

    it("shows ramp rate with 1 decimal place", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ rampRate: 3.5 })}
          yesterday={null}
        />,
      );
      expect(screen.getByText("3.5")).toBeInTheDocument();
    });
  });

  describe("delta function", () => {
    it("shows positive CTL delta with + sign", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: 65.5 })}
          yesterday={makeMetrics({ ctl: 64.0 })}
        />,
      );
      expect(screen.getByText("+1.5")).toBeInTheDocument();
    });

    it("shows negative CTL delta without + sign", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: 63.0 })}
          yesterday={makeMetrics({ ctl: 65.0 })}
        />,
      );
      expect(screen.getByText("-2.0")).toBeInTheDocument();
    });

    it("shows ±0 when delta is below 0.05 threshold", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: 65.04 })}
          yesterday={makeMetrics({ ctl: 65.0 })}
        />,
      );
      expect(screen.getByText("±0")).toBeInTheDocument();
    });

    it("shows ±0 for exact zero delta", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: 65.0 })}
          yesterday={makeMetrics({ ctl: 65.0 })}
        />,
      );
      expect(screen.getByText("±0")).toBeInTheDocument();
    });

    it("shows delta when |d| is above 0.05 threshold", () => {
      // delta = 65.1 - 65.0 = 0.1 > 0.05, so shows "+0.1"
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: 65.1 })}
          yesterday={makeMetrics({ ctl: 65.0 })}
        />,
      );
      expect(screen.getByText("+0.1")).toBeInTheDocument();
    });

    it("does not show delta when today CTL is null", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: null })}
          yesterday={makeMetrics({ ctl: 65.0 })}
        />,
      );
      // No delta row for CTL
      expect(screen.queryByText(/±0/)).not.toBeInTheDocument();
      expect(screen.queryByText(/\+/)).not.toBeInTheDocument();
    });

    it("does not show delta when yesterday is null", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ ctl: 65.0 })}
          yesterday={null}
        />,
      );
      expect(screen.queryByText(/±0/)).not.toBeInTheDocument();
    });

    it("shows delta for ATL independently", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ atl: 80.0 })}
          yesterday={makeMetrics({ atl: 75.0 })}
        />,
      );
      expect(screen.getByText("+5.0")).toBeInTheDocument();
    });

    it("never shows delta for Ramp metric", () => {
      render(
        <TrainingLoadCard
          today={makeMetrics({ rampRate: 5.0 })}
          yesterday={makeMetrics({ rampRate: 3.0 })}
        />,
      );
      // Ramp always passes delta={null} to Metric component
      // Only CTL and ATL deltas would show
      const dashes = screen.queryAllByText("±0");
      // No delta for ramp even though values differ
      expect(screen.queryByText("+2.0")).not.toBeInTheDocument();
    });
  });
});