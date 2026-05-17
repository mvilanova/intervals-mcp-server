import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeightForm } from "../WeightForm";
import type { WeightLog } from "@prisma/client";

// Mock the logWeight server action
vi.mock("../../actions/logging", () => ({
  logWeight: vi.fn(),
}));

// Mock useFormStatus since it requires a real form submission context
vi.mock("react-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-dom")>();
  return {
    ...actual,
    useFormStatus: vi.fn(() => ({ pending: false })),
  };
});

import { useFormStatus } from "react-dom";

const mockUseFormStatus = vi.mocked(useFormStatus);

function makeWeightLog(weightKg: number): WeightLog {
  return {
    id: "wl-1",
    userId: "user-1",
    date: new Date("2024-01-15"),
    weightKg,
    notes: null,
  };
}

describe("WeightForm", () => {
  beforeEach(() => {
    mockUseFormStatus.mockReturnValue({ pending: false } as ReturnType<typeof useFormStatus>);
  });

  describe("rendering", () => {
    it("renders the form heading", () => {
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByText("Log today's weight")).toBeInTheDocument();
    });

    it("renders weight input field", () => {
      render(<WeightForm todayWeight={null} />);
      const input = screen.getByRole("spinbutton");
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute("name", "weightKg");
      expect(input).toHaveAttribute("type", "number");
    });

    it("renders Save button", () => {
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    });

    it("does not show error when no error state", () => {
      render(<WeightForm todayWeight={null} />);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  describe("todayWeight prop", () => {
    it("shows saved weight when todayWeight is provided", () => {
      render(<WeightForm todayWeight={makeWeightLog(72.5)} />);
      expect(screen.getByText("saved 72.5 kg")).toBeInTheDocument();
    });

    it("does not show saved weight when todayWeight is null", () => {
      render(<WeightForm todayWeight={null} />);
      expect(screen.queryByText(/saved/)).not.toBeInTheDocument();
    });

    it("prefills input with today's weight", () => {
      render(<WeightForm todayWeight={makeWeightLog(72.5)} />);
      const input = screen.getByRole("spinbutton");
      expect(input).toHaveValue(72.5);
    });

    it("input has empty default when todayWeight is null", () => {
      render(<WeightForm todayWeight={null} />);
      const input = screen.getByRole("spinbutton");
      expect(input).toHaveValue(null);
    });
  });

  describe("input attributes", () => {
    it("has step=0.1 for decimal entry", () => {
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByRole("spinbutton")).toHaveAttribute("step", "0.1");
    });

    it("has min=30 constraint", () => {
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByRole("spinbutton")).toHaveAttribute("min", "30");
    });

    it("has max=250 constraint", () => {
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByRole("spinbutton")).toHaveAttribute("max", "250");
    });

    it("is required", () => {
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByRole("spinbutton")).toBeRequired();
    });
  });

  describe("submit button states", () => {
    it("button is enabled when not pending", () => {
      mockUseFormStatus.mockReturnValue({ pending: false } as ReturnType<typeof useFormStatus>);
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByRole("button")).not.toBeDisabled();
    });

    it("button shows Saving… text when pending", () => {
      mockUseFormStatus.mockReturnValue({ pending: true } as ReturnType<typeof useFormStatus>);
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByRole("button", { name: "Saving…" })).toBeInTheDocument();
    });

    it("button is disabled when pending", () => {
      mockUseFormStatus.mockReturnValue({ pending: true } as ReturnType<typeof useFormStatus>);
      render(<WeightForm todayWeight={null} />);
      expect(screen.getByRole("button")).toBeDisabled();
    });
  });
});