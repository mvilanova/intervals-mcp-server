import { z } from "zod";

// Intervals.icu wellness response. Most fields are optional / nullable —
// Intervals returns whichever the athlete has logged on a given day.
// We use `.passthrough()` so additional fields don't cause validation
// failures; we only persist the columns we care about.
export const WellnessEntry = z
  .object({
    // `id` is the date string (YYYY-MM-DD). Some endpoints return `date`
    // instead — we accept either.
    id: z.string().optional(),
    date: z.string().optional(),

    // Training metrics
    ctl: z.number().nullable().optional(),
    atl: z.number().nullable().optional(),
    rampRate: z.number().nullable().optional(),

    // Vitals
    weight: z.number().nullable().optional(),
    restingHR: z.number().nullable().optional(),
    hrv: z.number().nullable().optional(),

    // Sleep
    sleepSecs: z.number().nullable().optional(),
    sleepHours: z.number().nullable().optional(),
    sleepScore: z.number().nullable().optional(),

    // Activity
    steps: z.number().nullable().optional(),

    // Nutrition (logged in Intervals via MyFitnessPal etc.)
    kcalConsumed: z.number().nullable().optional(),
    carbohydrates: z.number().nullable().optional(),
    protein: z.number().nullable().optional(),
    fatTotal: z.number().nullable().optional(),
  })
  .passthrough();

export type WellnessEntry = z.infer<typeof WellnessEntry>;

// The endpoint sometimes returns an array, sometimes a date-keyed object.
// Both shapes are normalized to WellnessEntry[] in the sync code.
export const WellnessResponse = z.union([
  z.array(WellnessEntry),
  z.record(z.string(), WellnessEntry),
]);

export const ActivityEntry = z
  .object({
    id: z.union([z.string(), z.number()]),
    startTime: z.string().nullable().optional(),
    start_date: z.string().nullable().optional(),
    type: z.string().nullable().optional(),

    // Distance (meters) and time (seconds)
    distance: z.number().nullable().optional(),
    moving_time: z.number().nullable().optional(),
    elapsed_time: z.number().nullable().optional(),
    duration: z.number().nullable().optional(),

    // TSS-equivalent — Intervals exposes this under two keys.
    icu_training_load: z.number().nullable().optional(),
    trainingLoad: z.number().nullable().optional(),
  })
  .passthrough();

export type ActivityEntry = z.infer<typeof ActivityEntry>;

export const ActivityResponse = z.array(ActivityEntry);

export type SyncResult = {
  wellnessUpserts: number;
  activityUpserts: number;
  weightUpserts: number;
  startedAt: Date;
  finishedAt: Date;
  errors: string[];
};
