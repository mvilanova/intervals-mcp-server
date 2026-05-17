import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RecoveryCard } from "../RecoveryCard";
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

describe("RecoveryCard", () => {
  it("renders section heading", () => {
    render(<RecoveryCard today={null} baselineRhr={null} />);
    expect(screen.getByText("Recovery")).toBeInTheDocument();
  });

  describe("RHR display", () => {
    it("shows em-dash when today is null", () => {
      render(<RecoveryCard today={null} baselineRhr={null} />);
      // There should be em-dashes for RHR, HRV, and Sleep
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(3);
    });

    it("shows RHR value when available", () => {
      render(
        <RecoveryCard today={makeMetrics({ rhr: 52 })} baselineRhr={null} />,
      );
      expect(screen.getByText("52")).toBeInTheDocument();
    });

    it("shows em-dash for RHR when rhr is null", () => {
      render(
        <RecoveryCard today={makeMetrics({ rhr: null })} baselineRhr={null} />,
      );
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe("rhrDelta display", () => {
    it("shows positive delta vs baseline when rhr is above baseline", () => {
      render(
        <RecoveryCard
          today={makeMetrics({ rhr: 57 })}
          baselineRhr={52}
        />,
      );
      expect(screen.getByText("+5 vs baseline")).toBeInTheDocument();
    });

    it("shows negative delta vs baseline when rhr is below baseline", () => {
      render(
        <RecoveryCard
          today={makeMetrics({ rhr: 49 })}
          baselineRhr={52}
        />,
      );
      expect(screen.getByText("-3 vs baseline")).toBeInTheDocument();
    });

    it("shows = baseline when rhr equals baseline", () => {
      render(
        <RecoveryCard
          today={makeMetrics({ rhr: 52 })}
          baselineRhr={52}
        />,
      );
      expect(screen.getByText("= baseline")).toBeInTheDocument();
    });

    it("does not show delta when rhr is null", () => {
      render(
        <RecoveryCard today={makeMetrics({ rhr: null })} baselineRhr={52} />,
      );
      expect(screen.queryByText(/vs baseline/)).not.toBeInTheDocument();
      expect(screen.queryByText(/= baseline/)).not.toBeInTheDocument();
    });

    it("does not show delta when baseline is null", () => {
      render(
        <RecoveryCard today={makeMetrics({ rhr: 52 })} baselineRhr={null} />,
      );
      expect(screen.queryByText(/vs baseline/)).not.toBeInTheDocument();
    });

    it("does not show delta when both rhr and baseline are null", () => {
      render(<RecoveryCard today={null} baselineRhr={null} />);
      expect(screen.queryByText(/vs baseline/)).not.toBeInTheDocument();
    });
  });

  describe("HRV display", () => {
    it("shows em-dash when hrv is null", () => {
      render(
        <RecoveryCard today={makeMetrics({ hrv: null })} baselineRhr={null} />,
      );
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });

    it("shows HRV rounded to 0 decimal places", () => {
      render(
        <RecoveryCard today={makeMetrics({ hrv: 45.7 })} baselineRhr={null} />,
      );
      expect(screen.getByText("46")).toBeInTheDocument();
    });

    it("shows HRV as integer string when value is whole number", () => {
      render(
        <RecoveryCard today={makeMetrics({ hrv: 50.0 })} baselineRhr={null} />,
      );
      expect(screen.getByText("50")).toBeInTheDocument();
    });
  });

  describe("Sleep display", () => {
    it("shows em-dash when sleepHours is null", () => {
      render(
        <RecoveryCard
          today={makeMetrics({ sleepHours: null })}
          baselineRhr={null}
        />,
      );
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });

    it("shows sleep hours with 1 decimal and h suffix", () => {
      render(
        <RecoveryCard
          today={makeMetrics({ sleepHours: 7.5 })}
          baselineRhr={null}
        />,
      );
      expect(screen.getByText("7.5h")).toBeInTheDocument();
    });

    it("shows sleep score when available", () => {
      render(
        <RecoveryCard
          today={makeMetrics({ sleepHours: 7.5, sleepScore: 85 })}
          baselineRhr={null}
        />,
      );
      expect(screen.getByText("score 85")).toBeInTheDocument();
    });

    it("does not show sleep score when null", () => {
      render(
        <RecoveryCard
          today={makeMetrics({ sleepHours: 7.5, sleepScore: null })}
          baselineRhr={null}
        />,
      );
      expect(screen.queryByText(/score/)).not.toBeInTheDocument();
    });
  });

  describe("null today", () => {
    it("renders three em-dashes when today is null", () => {
      render(<RecoveryCard today={null} baselineRhr={null} />);
      const dashes = screen.getAllByText("—");
      expect(dashes).toHaveLength(3);
    });
  });

  describe("sparklines", () => {
    it("renders sleep sparkline polyline when dailyMetrics14d has 2+ sleepHours values", () => {
      const { container } = render(
        <RecoveryCard
          today={makeMetrics({ sleepHours: 7.5 })}
          baselineRhr={null}
          dailyMetrics14d={[
            makeMetrics({ sleepHours: 6.5 }),
            makeMetrics({ sleepHours: 7.0 }),
            makeMetrics({ sleepHours: 7.5 }),
          ]}
        />,
      );
      const polylines = container.querySelectorAll("polyline");
      expect(polylines).toHaveLength(1);
    });

    it("renders rhr, hrv and sleep sparklines when all have data", () => {
      const { container } = render(
        <RecoveryCard
          today={makeMetrics({ rhr: 52, hrv: 65, sleepHours: 7.5 })}
          baselineRhr={null}
          dailyMetrics14d={[
            makeMetrics({ rhr: 50, hrv: 60, sleepHours: 6.5 }),
            makeMetrics({ rhr: 51, hrv: 62, sleepHours: 7.0 }),
            makeMetrics({ rhr: 52, hrv: 65, sleepHours: 7.5 }),
          ]}
        />,
      );
      const polylines = container.querySelectorAll("polyline");
      expect(polylines.length).toBe(3);
    });

    it("does not render sparklines when dailyMetrics14d is absent", () => {
      const { container } = render(
        <RecoveryCard
          today={makeMetrics({ rhr: 52, hrv: 65, sleepHours: 7.5 })}
          baselineRhr={null}
        />,
      );
      expect(container.querySelectorAll("polyline")).toHaveLength(0);
    });
  });
});
