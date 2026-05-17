import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MealGrid } from "../MealGrid";
import type { MealLog } from "@prisma/client";

// Mock the logMeal server action
vi.mock("../../actions/logging", () => ({
  logMeal: vi.fn(),
}));

import { logMeal } from "../../actions/logging";

const mockLogMeal = vi.mocked(logMeal);

function makeMealLog(
  mealType: string,
  status: string,
  overrides: Partial<MealLog> = {},
): MealLog {
  return {
    id: `ml-${mealType}`,
    userId: "user-1",
    date: new Date("2024-01-15"),
    mealType,
    status,
    notes: null,
    ...overrides,
  } as MealLog;
}

describe("MealGrid", () => {
  beforeEach(() => {
    mockLogMeal.mockReset();
    mockLogMeal.mockResolvedValue({ ok: true });
  });

  describe("rendering", () => {
    it("renders section heading", () => {
      render(<MealGrid initial={[]} />);
      expect(screen.getByText("Meals")).toBeInTheDocument();
    });

    it("renders all four meal labels", () => {
      render(<MealGrid initial={[]} />);
      expect(screen.getByText("Breakfast")).toBeInTheDocument();
      expect(screen.getByText("Comida")).toBeInTheDocument();
      expect(screen.getByText("Merienda")).toBeInTheDocument();
      expect(screen.getByText("Cena")).toBeInTheDocument();
    });

    it("renders Hit, Partial, Missed buttons for each meal (12 total)", () => {
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      const partialButtons = screen.getAllByText("Partial");
      const missedButtons = screen.getAllByText("Missed");
      expect(hitButtons).toHaveLength(4);
      expect(partialButtons).toHaveLength(4);
      expect(missedButtons).toHaveLength(4);
    });

    it("does not show error message initially", () => {
      render(<MealGrid initial={[]} />);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  describe("initial state from props", () => {
    it("applies active class to the current status button for a meal", () => {
      render(
        <MealGrid initial={[makeMealLog("breakfast", "hit")]} />,
      );
      // Find buttons for breakfast row - the "Hit" button should be active
      const hitButtons = screen.getAllByText("Hit");
      // The first Hit button corresponds to Breakfast
      expect(hitButtons[0].className).toContain("bg-emerald-600");
    });

    it("applies amber active class for partial status", () => {
      render(
        <MealGrid initial={[makeMealLog("comida", "partial")]} />,
      );
      const partialButtons = screen.getAllByText("Partial");
      // Comida is the second meal, so partialButtons[1] should be active
      expect(partialButtons[1].className).toContain("bg-amber-500");
    });

    it("applies red active class for missed status", () => {
      render(
        <MealGrid initial={[makeMealLog("cena", "missed")]} />,
      );
      const missedButtons = screen.getAllByText("Missed");
      // Cena is the last meal (index 3)
      expect(missedButtons[3].className).toContain("bg-red-600");
    });

    it("inactive buttons have aria-pressed false", () => {
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      expect(hitButtons[0]).toHaveAttribute("aria-pressed", "false");
      expect(hitButtons[0].className).not.toContain("bg-emerald-600");
    });

    it("renders grouped status controls with accessible labels", () => {
      render(<MealGrid initial={[]} />);
      const breakfastGroup = screen.getByRole("group", { name: "Breakfast status" });
      expect(breakfastGroup).toBeInTheDocument();
      const cenaGroup = screen.getByRole("group", { name: "Cena status" });
      expect(cenaGroup).toBeInTheDocument();
    });

    it("active button has aria-pressed true, others false", () => {
      render(<MealGrid initial={[makeMealLog("breakfast", "hit")]} />);
      const hitButtons = screen.getAllByText("Hit");
      const partialButtons = screen.getAllByText("Partial");
      const missedButtons = screen.getAllByText("Missed");
      expect(hitButtons[0]).toHaveAttribute("aria-pressed", "true");
      expect(partialButtons[0]).toHaveAttribute("aria-pressed", "false");
      expect(missedButtons[0]).toHaveAttribute("aria-pressed", "false");
    });
  });

  describe("icon rendering", () => {
    it("each status button contains an svg icon", () => {
      render(<MealGrid initial={[]} />);
      const buttons = screen.getAllByRole("button");
      // 4 meals × 3 statuses = 12 buttons, each should have an SVG child
      expect(buttons).toHaveLength(12);
      buttons.forEach((btn) => {
        expect(btn.querySelector("svg")).not.toBeNull();
      });
    });

    it("svg icons are aria-hidden so they are invisible to screen readers", () => {
      render(<MealGrid initial={[]} />);
      const buttons = screen.getAllByRole("button");
      buttons.forEach((btn) => {
        const svg = btn.querySelector("svg");
        expect(svg).toHaveAttribute("aria-hidden", "true");
      });
    });

    it("hit button svg has correct viewBox", () => {
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      const svg = hitButtons[0].querySelector("svg");
      expect(svg).toHaveAttribute("viewBox", "0 0 14 14");
      expect(svg).toHaveAttribute("width", "14");
      expect(svg).toHaveAttribute("height", "14");
    });

    it("partial button svg has correct viewBox", () => {
      render(<MealGrid initial={[]} />);
      const partialButtons = screen.getAllByText("Partial");
      const svg = partialButtons[0].querySelector("svg");
      expect(svg).toHaveAttribute("viewBox", "0 0 14 14");
    });

    it("missed button svg has correct viewBox", () => {
      render(<MealGrid initial={[]} />);
      const missedButtons = screen.getAllByText("Missed");
      const svg = missedButtons[0].querySelector("svg");
      expect(svg).toHaveAttribute("viewBox", "0 0 14 14");
    });

    it("icons remain present after a meal status is activated", async () => {
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      fireEvent.click(hitButtons[0]);
      await waitFor(() => {
        expect(mockLogMeal).toHaveBeenCalled();
      });
      // SVG should still be in the active button
      expect(hitButtons[0].querySelector("svg")).not.toBeNull();
    });
  });

  describe("button and layout styling", () => {
    it("active hit button does not have border-emerald-600 class (border removed in PR)", () => {
      render(<MealGrid initial={[makeMealLog("breakfast", "hit")]} />);
      const hitButtons = screen.getAllByText("Hit");
      expect(hitButtons[0].className).not.toContain("border-emerald-600");
    });

    it("active partial button does not have border-amber-500 class (border removed in PR)", () => {
      render(<MealGrid initial={[makeMealLog("comida", "partial")]} />);
      const partialButtons = screen.getAllByText("Partial");
      expect(partialButtons[1].className).not.toContain("border-amber-500");
    });

    it("active missed button does not have border-red-600 class (border removed in PR)", () => {
      render(<MealGrid initial={[makeMealLog("cena", "missed")]} />);
      const missedButtons = screen.getAllByText("Missed");
      expect(missedButtons[3].className).not.toContain("border-red-600");
    });

    it("inactive buttons do not have border-gray-300 class (old inactive style removed)", () => {
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      expect(hitButtons[0].className).not.toContain("border-gray-300");
    });

    it("inactive buttons have text-muted-foreground class", () => {
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      expect(hitButtons[0].className).toContain("text-muted-foreground");
    });

    it("buttons have min-h-[44px] for touch accessibility", () => {
      render(<MealGrid initial={[]} />);
      const buttons = screen.getAllByRole("button");
      buttons.forEach((btn) => {
        expect(btn.className).toContain("min-h-[44px]");
      });
    });

    it("status group container uses flex layout, not grid", () => {
      render(<MealGrid initial={[]} />);
      const group = screen.getByRole("group", { name: "Breakfast status" });
      expect(group.className).toContain("flex");
      expect(group.className).not.toContain("grid-cols-3");
    });

    it("status group container has rounded-md and border classes", () => {
      render(<MealGrid initial={[]} />);
      const group = screen.getByRole("group", { name: "Breakfast status" });
      expect(group.className).toContain("rounded-md");
      expect(group.className).toContain("border");
    });

    it("meal label has text-muted-foreground class", () => {
      render(<MealGrid initial={[]} />);
      const label = screen.getByText("Breakfast");
      expect(label.className).toContain("text-muted-foreground");
    });

    it("all four meal labels have text-muted-foreground class", () => {
      render(<MealGrid initial={[]} />);
      ["Breakfast", "Comida", "Merienda", "Cena"].forEach((meal) => {
        expect(screen.getByText(meal).className).toContain("text-muted-foreground");
      });
    });

    it("buttons have flex-1 class for equal sizing in segmented control", () => {
      render(<MealGrid initial={[]} />);
      const buttons = screen.getAllByRole("button");
      buttons.forEach((btn) => {
        expect(btn.className).toContain("flex-1");
      });
    });

    it("all four meal groups use flex layout", () => {
      render(<MealGrid initial={[]} />);
      const groups = screen.getAllByRole("group");
      groups.forEach((group) => {
        expect(group.className).toContain("flex");
      });
    });
  });

  describe("click interactions", () => {
    it("calls logMeal with correct mealType and status on button click", async () => {
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");

      fireEvent.click(hitButtons[0]); // Breakfast Hit
      await waitFor(() => {
        expect(mockLogMeal).toHaveBeenCalledWith("breakfast", "hit");
      });
    });

    it("calls logMeal with comida and missed when clicking comida missed", async () => {
      render(<MealGrid initial={[]} />);
      const missedButtons = screen.getAllByText("Missed");
      fireEvent.click(missedButtons[1]); // Comida Missed
      await waitFor(() => {
        expect(mockLogMeal).toHaveBeenCalledWith("comida", "missed");
      });
    });

    it("does not show error when logMeal succeeds", async () => {
      mockLogMeal.mockResolvedValue({ ok: true });
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      fireEvent.click(hitButtons[0]);
      await waitFor(() => {
        expect(mockLogMeal).toHaveBeenCalled();
      });
      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });

    it("shows error message when logMeal returns error", async () => {
      mockLogMeal.mockResolvedValue({
        ok: false,
        error: "Something went wrong",
      });
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      fireEvent.click(hitButtons[0]);
      await waitFor(() => {
        expect(screen.getByText("Something went wrong")).toBeInTheDocument();
      });
    });

    it("clears previous error on new click", async () => {
      mockLogMeal
        .mockResolvedValueOnce({ ok: false, error: "Error occurred" })
        .mockResolvedValueOnce({ ok: true });

      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");

      // First click causes error
      fireEvent.click(hitButtons[0]);
      await waitFor(() => {
        expect(screen.getByText("Error occurred")).toBeInTheDocument();
      });

      // Second click clears error
      fireEvent.click(hitButtons[1]);
      await waitFor(() => {
        expect(screen.queryByText("Error occurred")).not.toBeInTheDocument();
      });
    });
  });
});