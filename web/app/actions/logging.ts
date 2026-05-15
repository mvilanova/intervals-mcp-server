"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { COOKIE_NAME, verifySession } from "@/lib/auth";

const MEAL_TYPES = ["breakfast", "comida", "merienda", "cena"] as const;
const MEAL_STATUSES = ["hit", "partial", "missed"] as const;

export type MealType = (typeof MEAL_TYPES)[number];
export type MealStatus = (typeof MEAL_STATUSES)[number];

const WeightInput = z.object({
  weightKg: z.coerce
    .number()
    .min(30, "Weight must be at least 30 kg")
    .max(250, "Weight must be at most 250 kg")
    .transform((n) => Math.round(n * 10) / 10),
});

const MealInput = z.object({
  mealType: z.enum(MEAL_TYPES),
  status: z.enum(MEAL_STATUSES),
});

export type ActionResult =
  | { ok: true }
  | { ok: false; error: string };

async function requireUser() {
  const jar = await cookies();
  if (!verifySession(jar.get(COOKIE_NAME)?.value)) {
    redirect("/login");
  }
  const user = await prisma.user.findFirst({
    orderBy: { createdAt: "asc" },
  });
  if (!user) {
    throw new Error("No user seeded");
  }
  return user;
}

function todayUTC(): Date {
  const now = new Date();
  return new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
  );
}

export async function logWeight(
  _prev: ActionResult | null,
  formData: FormData,
): Promise<ActionResult> {
  const parsed = WeightInput.safeParse({
    weightKg: formData.get("weightKg"),
  });
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid weight" };
  }

  const user = await requireUser();
  const date = todayUTC();

  // The sync's upsertWeightFromWellness only overwrites rows where notes
  // equals "from intervals" (lib/sync/intervals.ts:167). Leaving notes
  // empty here marks the row as a manual entry and protects it from
  // future Intervals syncs.
  await prisma.weightLog.upsert({
    where: { userId_date: { userId: user.id, date } },
    update: { weightKg: parsed.data.weightKg, notes: null },
    create: { userId: user.id, date, weightKg: parsed.data.weightKg },
  });

  revalidatePath("/");
  return { ok: true };
}

export async function logMeal(
  mealType: MealType,
  status: MealStatus,
): Promise<ActionResult> {
  const parsed = MealInput.safeParse({ mealType, status });
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid meal" };
  }

  const user = await requireUser();
  const date = todayUTC();

  await prisma.mealLog.upsert({
    where: {
      userId_date_mealType: {
        userId: user.id,
        date,
        mealType: parsed.data.mealType,
      },
    },
    update: { status: parsed.data.status },
    create: {
      userId: user.id,
      date,
      mealType: parsed.data.mealType,
      status: parsed.data.status,
    },
  });

  revalidatePath("/");
  return { ok: true };
}
