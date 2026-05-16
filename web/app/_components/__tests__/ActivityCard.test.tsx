import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ActivityCard } from "../ActivityCard";
import type { Activity } from "@prisma/client";

function makeActivity(overrides: Partial<Activity> = {}): Activity {
  return {
    id: "act-1",
    userId: "user-1",
    date: new Date("2024-01-15"),
    type: "Run",
    durationMin: 60,
    distanceKm: null,
    tss: null,
    externalId: null,
    name: null,
    description: null,
    ...overrides,
  };
}

describe("ActivityCard", () => {
  describe("empty state", () => {
    it("renders rest day message when no activities", () => {
      render(<ActivityCard activities={[]} />);
      expect(
        screen.getByText("Rest day — no activities logged."),
      ).toBeInTheDocument();
    });

    it("renders section heading", () => {
      render(<ActivityCard activities={[]} />);
      expect(screen.getByText("Today's training")).toBeInTheDocument();
    });
  });

  describe("activity list", () => {
    it("renders activity type", () => {
      render(<ActivityCard activities={[makeActivity({ type: "Ride" })]} />);
      expect(screen.getByText("Ride")).toBeInTheDocument();
    });

    it("renders multiple activities", () => {
      render(
        <ActivityCard
          activities={[
            makeActivity({ id: "act-1", type: "Run" }),
            makeActivity({ id: "act-2", type: "Swim" }),
          ]}
        />,
      );
      expect(screen.getByText("Run")).toBeInTheDocument();
      expect(screen.getByText("Swim")).toBeInTheDocument();
    });
  });

  describe("fmtDuration formatting", () => {
    it("shows em-dash for null duration", () => {
      render(<ActivityCard activities={[makeActivity({ durationMin: null })]} />);
      expect(screen.getByText("—")).toBeInTheDocument();
    });

    it("shows minutes only when under 60", () => {
      render(<ActivityCard activities={[makeActivity({ durationMin: 45 })]} />);
      expect(screen.getByText(/45m/)).toBeInTheDocument();
    });

    it("shows 0m for zero duration", () => {
      render(<ActivityCard activities={[makeActivity({ durationMin: 0 })]} />);
      expect(screen.getByText(/0m/)).toBeInTheDocument();
    });

    it("shows hours only when exact multiple of 60", () => {
      render(<ActivityCard activities={[makeActivity({ durationMin: 60 })]} />);
      expect(screen.getByText(/1h$/)).toBeInTheDocument();
    });

    it("shows hours and minutes for non-exact hours", () => {
      render(<ActivityCard activities={[makeActivity({ durationMin: 90 })]} />);
      expect(screen.getByText(/1h 30m/)).toBeInTheDocument();
    });

    it("shows 2h for 120 minutes", () => {
      render(<ActivityCard activities={[makeActivity({ durationMin: 120 })]} />);
      expect(screen.getByText(/2h$/)).toBeInTheDocument();
    });

    it("rounds 119.7 minutes to 2h instead of splitting as 1h 60m", () => {
      // 119.7 rounds to 120 min -> 2h, not 1h 60m
      render(<ActivityCard activities={[makeActivity({ durationMin: 119.7 })]} />);
      expect(screen.getByText(/2h$/)).toBeInTheDocument();
      expect(screen.queryByText(/60m/)).not.toBeInTheDocument();
    });

    it("rounds 59.7 minutes to 60m displayed as 1h", () => {
      render(<ActivityCard activities={[makeActivity({ durationMin: 59.7 })]} />);
      expect(screen.getByText(/1h$/)).toBeInTheDocument();
    });
  });

  describe("optional fields", () => {
    it("shows distance when distanceKm is provided", () => {
      render(
        <ActivityCard
          activities={[makeActivity({ durationMin: 30, distanceKm: 5.123 })]}
        />,
      );
      expect(screen.getByText(/5\.1 km/)).toBeInTheDocument();
    });

    it("does not show distance separator when distanceKm is null", () => {
      render(<ActivityCard activities={[makeActivity({ distanceKm: null })]} />);
      expect(screen.queryByText(/km/)).not.toBeInTheDocument();
    });

    it("shows TSS when tss is provided", () => {
      render(
        <ActivityCard activities={[makeActivity({ durationMin: 30, tss: 75.4 })]} />,
      );
      expect(screen.getByText(/75 TSS/)).toBeInTheDocument();
    });

    it("does not show TSS when tss is null", () => {
      render(<ActivityCard activities={[makeActivity({ tss: null })]} />);
      expect(screen.queryByText(/TSS/)).not.toBeInTheDocument();
    });

    it("shows both distance and TSS when both are provided", () => {
      render(
        <ActivityCard
          activities={[
            makeActivity({ durationMin: 60, distanceKm: 10.0, tss: 100 }),
          ]}
        />,
      );
      expect(screen.getByText(/10\.0 km/)).toBeInTheDocument();
      expect(screen.getByText(/100 TSS/)).toBeInTheDocument();
    });
  });
});