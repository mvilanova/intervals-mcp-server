"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import type { WeightLog } from "@prisma/client";
import { logWeight } from "../actions/logging";
import type { ActionResult } from "../actions/logging";

type Props = {
  todayWeight: WeightLog | null;
};

export function WeightForm({ todayWeight }: Props) {
  const [state, formAction] = useActionState<ActionResult | null, FormData>(
    logWeight,
    null,
  );

  return (
    <form action={formAction} className="space-y-2">
      <div className="flex items-baseline gap-2">
        <h3 className="text-sm font-medium">Log today&apos;s weight</h3>
        {todayWeight ? (
          <span className="text-xs text-emerald-600 dark:text-emerald-400">
            saved {todayWeight.weightKg.toFixed(1)} kg
          </span>
        ) : null}
      </div>
      <div className="flex gap-2">
        <input
          id="weightKg-input"
          name="weightKg"
          type="number"
          inputMode="decimal"
          step="0.1"
          min="30"
          max="250"
          required
          defaultValue={todayWeight?.weightKg ?? ""}
          placeholder="kg"
          aria-label="Weight in kilograms"
          aria-describedby={state?.ok === false ? "weightKg-error" : undefined}
          aria-invalid={state?.ok === false || undefined}
          className="flex-1 rounded border border-gray-300 dark:border-gray-700 bg-transparent px-3 py-2 text-base tabular-nums"
        />
        <SubmitButton />
      </div>
      {state?.ok === false ? (
        <p
          id="weightKg-error"
          role="alert"
          aria-live="polite"
          className="text-xs text-red-600"
        >
          {state.error}
        </p>
      ) : null}
    </form>
  );
}

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="rounded bg-black px-4 py-2 text-white text-sm disabled:opacity-50"
    >
      {pending ? "Saving…" : "Save"}
    </button>
  );
}
