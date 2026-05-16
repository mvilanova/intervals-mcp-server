"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/db";
import { COOKIE_NAME, verifySession } from "@/lib/auth";
import { regenerateDailySummary } from "@/lib/ai/summarize";

function todayUTC(): Date {
  const now = new Date();
  return new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
  );
}

export async function regenerateSummaryAction(): Promise<void> {
  const jar = await cookies();
  if (!verifySession(jar.get(COOKIE_NAME)?.value)) {
    redirect("/login");
  }
  const user = await prisma.user.findFirst({
    orderBy: { createdAt: "asc" },
  });
  if (!user) return;

  await regenerateDailySummary(user.id, todayUTC());
  revalidatePath("/");
}
