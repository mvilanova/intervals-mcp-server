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

    it("inactive buttons have border-gray-300 class", () => {
      render(<MealGrid initial={[]} />);
      const hitButtons = screen.getAllByText("Hit");
      expect(hitButtons[0].className).toContain("border-gray-300");
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