import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeightCard } from "../WeightCard";
import type { WeightLog } from "@prisma/client";

function makeWeightLog(
  weightKg: number,
  overrides: Partial<WeightLog> = {},
): WeightLog {
  return {
    id: "wl-1",
    userId: "user-1",
    date: new Date("2024-01-15"),
    weightKg,
    notes: null,
    ...overrides,
  };
}

describe("WeightCard", () => {
  it("renders section heading", () => {
    render(
      <WeightCard
        latest={null}
        weekAgo={null}
        daysAgo={null}
        targetWeight={null}
        targetDate={null}
      />,
    );
    expect(screen.getByText("Weight")).toBeInTheDocument();
  });

  describe("no weight data", () => {
    it("shows em-dash when latest is null", () => {
      render(
        <WeightCard
          latest={null}
          weekAgo={null}
          daysAgo={null}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.getByText("—")).toBeInTheDocument();
    });

    it("shows kg unit label even without weight", () => {
      render(
        <WeightCard
          latest={null}
          weekAgo={null}
          daysAgo={null}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.getByText("kg")).toBeInTheDocument();
    });
  });

  describe("weight display", () => {
    it("shows current weight with 1 decimal place", () => {
      render(
        <WeightCard
          latest={makeWeightLog(72.3)}
          weekAgo={null}
          daysAgo={0}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.getByText("72.3")).toBeInTheDocument();
    });

    it("shows 'today' when daysAgo is 0", () => {
      render(
        <WeightCard
          latest={makeWeightLog(72.3)}
          weekAgo={null}
          daysAgo={0}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.getByText("today")).toBeInTheDocument();
    });

    it("shows days ago when daysAgo > 0", () => {
      render(
        <WeightCard
          latest={makeWeightLog(72.3)}
          weekAgo={null}
          daysAgo={3}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.getByText("3d ago")).toBeInTheDocument();
    });

    it("does not show days ago when latest is null", () => {
      render(
        <WeightCard
          latest={null}
          weekAgo={null}
          daysAgo={3}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.queryByText(/ago/)).not.toBeInTheDocument();
    });
  });

  describe("7-day delta", () => {
    it("shows 7d delta with em-dash when no weekAgo", () => {
      const { container } = render(
        <WeightCard
          latest={makeWeightLog(72.3)}
          weekAgo={null}
          daysAgo={0}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.getByText(/7d:/)).toBeInTheDocument();
      // The em-dash is a text node inside the span alongside "7d: " text
      expect(container.textContent).toContain("—");
    });

    it("shows negative delta in emerald color class when weight decreased", () => {
      render(
        <WeightCard
          latest={makeWeightLog(71.0)}
          weekAgo={makeWeightLog(72.5)}
          daysAgo={0}
          targetWeight={null}
          targetDate={null}
        />,
      );
      const delta = screen.getByText("-1.5 kg");
      expect(delta).toBeInTheDocument();
      expect(delta).toHaveClass("text-emerald-600");
    });

    it("shows positive delta without emerald class when weight increased", () => {
      render(
        <WeightCard
          latest={makeWeightLog(73.5)}
          weekAgo={makeWeightLog(72.0)}
          daysAgo={0}
          targetWeight={null}
          targetDate={null}
        />,
      );
      const delta = screen.getByText("+1.5 kg");
      expect(delta).toBeInTheDocument();
      expect(delta).not.toHaveClass("text-emerald-600");
    });

    it("shows zero delta as 0.0 when weight unchanged (d=0 has no + sign)", () => {
      // fmtDelta(0) = "" + "0.0" = "0.0" since d=0 is not > 0
      const { container } = render(
        <WeightCard
          latest={makeWeightLog(72.0)}
          weekAgo={makeWeightLog(72.0)}
          daysAgo={0}
          targetWeight={null}
          targetDate={null}
        />,
      );
      // The delta span contains "0.0" and " kg" as separate text nodes
      expect(container.textContent).toContain("0.0");
      expect(container.textContent).toContain("kg");
    });
  });

  describe("target weight", () => {
    it("shows target weight with 1 decimal", () => {
      render(
        <WeightCard
          latest={null}
          weekAgo={null}
          daysAgo={null}
          targetWeight={70.0}
          targetDate={null}
        />,
      );
      expect(screen.getByText(/70\.0 kg/)).toBeInTheDocument();
    });

    it("shows target with remaining delta when latest is provided", () => {
      render(
        <WeightCard
          latest={makeWeightLog(72.5)}
          weekAgo={null}
          daysAgo={0}
          targetWeight={70.0}
          targetDate={null}
        />,
      );
      // toTarget = 72.5 - 70.0 = 2.5, formatted as +2.5
      expect(screen.getByText(/\(\+2\.5\)/)).toBeInTheDocument();
    });

    it("shows negative toTarget delta when already below target", () => {
      render(
        <WeightCard
          latest={makeWeightLog(68.0)}
          weekAgo={null}
          daysAgo={0}
          targetWeight={70.0}
          targetDate={null}
        />,
      );
      // toTarget = 68.0 - 70.0 = -2.0, formatted as -2.0
      expect(screen.getByText(/\(-2\.0\)/)).toBeInTheDocument();
    });

    it("shows em-dash for target when targetWeight is null", () => {
      render(
        <WeightCard
          latest={makeWeightLog(72.5)}
          weekAgo={null}
          daysAgo={0}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.getByText(/target: —/)).toBeInTheDocument();
    });
  });

  describe("target date", () => {
    it("shows target date when provided", () => {
      render(
        <WeightCard
          latest={null}
          weekAgo={null}
          daysAgo={null}
          targetWeight={70.0}
          targetDate={new Date("2024-06-01T00:00:00.000Z")}
        />,
      );
      expect(screen.getByText("by 2024-06-01")).toBeInTheDocument();
    });

    it("does not show target date when null", () => {
      render(
        <WeightCard
          latest={null}
          weekAgo={null}
          daysAgo={null}
          targetWeight={null}
          targetDate={null}
        />,
      );
      expect(screen.queryByText(/^by /)).not.toBeInTheDocument();
    });
  });
});