"use client";

import { useOptimistic, useState, useTransition } from "react";
import type { MealLog } from "@prisma/client";
import { logMeal } from "../actions/logging";
import type { MealStatus, MealType } from "../actions/logging";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

const MEALS: { type: MealType; label: string }[] = [
  { type: "breakfast", label: "Breakfast" },
  { type: "comida", label: "Comida" },
  { type: "merienda", label: "Merienda" },
  { type: "cena", label: "Cena" },
];

const STATUSES: { value: MealStatus; label: string; activeClass: string }[] = [
  {
    value: "hit",
    label: "Hit",
    activeClass: "bg-emerald-600 text-white border-emerald-600",
  },
  {
    value: "partial",
    label: "Partial",
    activeClass: "bg-amber-500 text-white border-amber-500",
  },
  {
    value: "missed",
    label: "Missed",
    activeClass: "bg-red-600 text-white border-red-600",
  },
];

type Optimistic = { mealType: MealType; status: MealStatus };

type Props = {
  initial: MealLog[];
};

export function MealGrid({ initial }: Props) {
  const [optimistic, setOptimistic] = useOptimistic<MealLog[], Optimistic>(
    initial,
    (state, { mealType, status }) => {
      const others = state.filter((m) => m.mealType !== mealType);
      return [
        ...others,
        {
          // Synthetic record — only mealType + status matter for render.
          id: `optimistic-${mealType}`,
          userId: "",
          date: new Date(),
          mealType,
          status,
          notes: null,
        },
      ];
    },
  );
  const [, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  // Per-meal-type gate: serializes writes for the same meal so rapid taps
  // (hit → partial → missed) can't persist out of order when server calls
  // resolve in a different order from the clicks. Per-meal rather than
  // global so the user can still log multiple meals concurrently.
  const [pending, setPending] = useState<Set<MealType>>(new Set());

  const currentStatus = (type: MealType): MealStatus | null => {
    const found = optimistic.find((m) => m.mealType === type);
    return (found?.status as MealStatus | undefined) ?? null;
  };

  const handleClick = (mealType: MealType, status: MealStatus) => {
    if (pending.has(mealType)) return;
    setPending((prev) => new Set(prev).add(mealType));
    startTransition(async () => {
      setError(null);
      setOptimistic({ mealType, status });
      try {
        const result = await logMeal(mealType, status);
        if (!result.ok) setError(result.error);
      } catch {
        setError("Could not save meal. Please try again.");
      } finally {
        setPending((prev) => {
          const next = new Set(prev);
          next.delete(mealType);
          return next;
        });
      }
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Meals</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          {MEALS.map(({ type, label }) => {
            const active = currentStatus(type);
            const isPending = pending.has(type);
            return (
              <div key={type} className="grid grid-cols-[6rem_1fr] items-center gap-2">
                <div className="text-sm">{label}</div>
                <div
                  role="group"
                  aria-label={`${label} status`}
                  aria-busy={isPending}
                  className="grid grid-cols-3 gap-1.5"
                >
                  {STATUSES.map(({ value, label: btnLabel, activeClass }) => {
                    const isActive = active === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => handleClick(type, value)}
                        disabled={isPending}
                        aria-pressed={isActive}
                        className={`rounded border px-2 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                          isActive
                            ? activeClass
                            : "border-gray-300 dark:border-gray-700 text-gray-700 dark:text-gray-300"
                        }`}
                      >
                        {btnLabel}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
        {error ? (
          <p role="alert" aria-live="polite" className="text-xs text-red-600">
            {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
