"use client";

import React, { useOptimistic, useState, useTransition } from "react";
import type { MealLog } from "@prisma/client";
import { logMeal } from "../actions/logging";
import type { MealStatus, MealType } from "../actions/logging";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

function CheckIcon() {
  return (
    <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M2 7L5.5 10.5L12 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PartialIcon() {
  return (
    <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="5.5" stroke="currentColor" strokeWidth="2" />
      <path d="M4.5 7H9.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function CrossIcon() {
  return (
    <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 3L11 11M11 3L3 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

const MEALS: { type: MealType; label: string }[] = [
  { type: "breakfast", label: "Breakfast" },
  { type: "comida", label: "Comida" },
  { type: "merienda", label: "Merienda" },
  { type: "cena", label: "Cena" },
];

const STATUSES: {
  value: MealStatus;
  label: string;
  activeClass: string;
  Icon: () => React.ReactElement;
}[] = [
  {
    value: "hit",
    label: "Hit",
    activeClass: "bg-emerald-600 text-white",
    Icon: CheckIcon,
  },
  {
    value: "partial",
    label: "Partial",
    activeClass: "bg-amber-500 text-white",
    Icon: PartialIcon,
  },
  {
    value: "missed",
    label: "Missed",
    activeClass: "bg-red-600 text-white",
    Icon: CrossIcon,
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
                <div className="text-sm text-muted-foreground">{label}</div>
                <div
                  role="group"
                  aria-label={`${label} status`}
                  aria-busy={isPending}
                  className="flex rounded-md border border-input divide-x divide-input overflow-hidden"
                >
                  {STATUSES.map(({ value, label: btnLabel, activeClass, Icon }) => {
                    const isActive = active === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => handleClick(type, value)}
                        disabled={isPending}
                        aria-pressed={isActive}
                        className={`flex-1 inline-flex items-center justify-center gap-1.5 min-h-[44px] px-2 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-60 ${
                          isActive
                            ? activeClass
                            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                        }`}
                      >
                        <Icon />
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
