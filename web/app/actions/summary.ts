"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { COOKIE_NAME, verifySession } from "@/lib/auth";
import { regenerateDailySummary } from "@/lib/ai/summarize";

function todayUTC(): Date {
  const now = new Date();
  return new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()),
  );
}

// `userId` is bound by the calling card via `.bind()` so the refresh
// acts on the exact user whose summary the card rendered. The bound
// value is client-tamperable in principle; safe here because the project
// is single-user v1 and the session cookie doesn't yet bind to a user.
// When multi-tenant lands, this needs to verify userId matches the
// session-resolved user id.
export async function regenerateSummaryAction(userId: string): Promise<void> {
  const jar = await cookies();
  if (!verifySession(jar.get(COOKIE_NAME)?.value)) {
    redirect("/login");
  }
  await regenerateDailySummary(userId, todayUTC());
  revalidatePath("/");
}
