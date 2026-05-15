"use client";

import { useOptimistic, useState, useTransition } from "react";
import type { MealLog } from "@prisma/client";
import { logMeal } from "../actions/logging";
import type { MealStatus, MealType } from "../actions/logging";

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

  const currentStatus = (type: MealType): MealStatus | null => {
    const found = optimistic.find((m) => m.mealType === type);
    return (found?.status as MealStatus | undefined) ?? null;
  };

  const handleClick = (mealType: MealType, status: MealStatus) => {
    startTransition(async () => {
      setError(null);
      setOptimistic({ mealType, status });
      const result = await logMeal(mealType, status);
      if (!result.ok) {
        setError(result.error);
      }
    });
  };

  return (
    <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
      <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">
        Meals
      </h2>
      <div className="space-y-2">
        {MEALS.map(({ type, label }) => {
          const active = currentStatus(type);
          return (
            <div key={type} className="grid grid-cols-[6rem_1fr] items-center gap-2">
              <div className="text-sm">{label}</div>
              <div className="grid grid-cols-3 gap-1.5">
                {STATUSES.map(({ value, label: btnLabel, activeClass }) => {
                  const isActive = active === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => handleClick(type, value)}
                      className={`rounded border px-2 py-1.5 text-xs font-medium transition-colors ${
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
      {error ? <p className="text-xs text-red-600">{error}</p> : null}
    </section>
  );
}
