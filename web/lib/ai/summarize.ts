import "server-only";
import Anthropic from "@anthropic-ai/sdk";
import type {
  Activity,
  DailyMetrics,
  DailySummary,
  MealLog,
  User,
  WeightLog,
} from "@prisma/client";
import { prisma } from "@/lib/db";

const MODEL = "claude-sonnet-4-6";
const MAX_TOKENS = 200;
// 30s for a ~200-token call is generous (typical: 1–3s). The SDK default
// of 10 minutes would hang the user's page render on a stuck call.
const REQUEST_TIMEOUT_MS = 30_000;
const MAX_RETRIES = 2;

const SYSTEM_PROMPT = `You summarize one day of personal health and training data for the user. Output 1–2 sentences, conversational second person, under 40 words. Pick the most actionable signal — don't list every field. Mention weight only when noteworthy (logged today, hit/missed target trend). Mention training load when it's climbing, falling, or freshly elevated. If recovery is poor (RHR up, sleep short), say so. If a meal type was missed, call it out gently. No greeting, no "today you...", no markdown.`;

let client: Anthropic | null = null;
function getClient(): Anthropic | null {
  if (!process.env.ANTHROPIC_API_KEY) return null;
  if (!client) {
    client = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY,
      timeout: REQUEST_TIMEOUT_MS,
      maxRetries: MAX_RETRIES,
    });
  }
  return client;
}

export function isEnabled(): boolean {
  return Boolean(process.env.ANTHROPIC_API_KEY);
}

type GenInput = {
  summaryDate: Date;
  user: Pick<User, "targetWeight" | "targetDate" | "baselineRhr">;
  today: DailyMetrics | null;
  yesterday: DailyMetrics | null;
  todayActivities: Activity[];
  todayMealLogs: MealLog[];
  latestWeight: WeightLog | null;
  weightWeekAgo: WeightLog | null;
};

function fmt(n: number | null | undefined, digits = 1): string {
  return n == null ? "—" : n.toFixed(digits);
}

function buildUserMessage(input: GenInput): string {
  const { summaryDate, user, today, yesterday, todayActivities, todayMealLogs, latestWeight, weightWeekAgo } = input;

  const ctlDelta =
    today?.ctl != null && yesterday?.ctl != null
      ? (today.ctl - yesterday.ctl).toFixed(1)
      : "—";

  const weightDelta =
    latestWeight && weightWeekAgo
      ? (latestWeight.weightKg - weightWeekAgo.weightKg).toFixed(1)
      : "—";

  const weightToTarget =
    latestWeight && user.targetWeight != null
      ? (latestWeight.weightKg - user.targetWeight).toFixed(1)
      : "—";

  // Anchor on summaryDate (not Date.now()) so regenerating the same day
  // later — or generating a historical day — produces a stable output.
  const targetDays =
    user.targetDate
      ? Math.round(
          (user.targetDate.getTime() - summaryDate.getTime()) /
            (1000 * 60 * 60 * 24),
        )
      : null;

  const meals = todayMealLogs.length
    ? todayMealLogs.map((m) => `${m.mealType}=${m.status}`).join(", ")
    : "none logged";

  const activities = todayActivities.length
    ? todayActivities
        .map((a) => `${a.type} ${a.durationMin}min ${a.tss ?? 0}TSS`)
        .join("; ")
    : "rest day";

  return [
    `Training: CTL ${fmt(today?.ctl ?? null)} (Δ vs yesterday: ${ctlDelta}), ATL ${fmt(today?.atl ?? null)}, ramp ${fmt(today?.rampRate ?? null)}`,
    `Activities today: ${activities}`,
    `Recovery: RHR ${fmt(today?.rhr ?? null, 0)} (baseline ${fmt(user.baselineRhr ?? null, 0)}), HRV ${fmt(today?.hrv ?? null, 0)}, sleep ${fmt(today?.sleepHours ?? null)}h (score ${fmt(today?.sleepScore ?? null, 0)})`,
    `Weight: latest ${latestWeight ? `${latestWeight.weightKg}kg` : "not logged"}, Δ vs 7d ago: ${weightDelta}kg, target ${user.targetWeight ?? "—"}kg (${weightToTarget}kg away${targetDays != null ? `, ${targetDays}d to target date` : ""})`,
    `Meals (breakfast/comida/merienda/cena): ${meals}`,
  ].join("\n");
}

async function callClaude(input: GenInput): Promise<string> {
  const c = getClient();
  if (!c) throw new Error("ANTHROPIC_API_KEY not set");

  const message = await c.messages.create({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: SYSTEM_PROMPT,
    messages: [{ role: "user", content: buildUserMessage(input) }],
  });

  const text = message.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("")
    .trim();

  if (!text) throw new Error("Empty summary from Claude");
  return text;
}

async function loadInput(userId: string, date: Date): Promise<GenInput | null> {
  const dayBefore = new Date(date);
  dayBefore.setUTCDate(dayBefore.getUTCDate() - 1);
  const weekAgo = new Date(date);
  weekAgo.setUTCDate(weekAgo.getUTCDate() - 7);

  const [user, today, yesterday, todayActivities, todayMealLogs, latestWeight, weightWeekAgo] =
    await Promise.all([
      prisma.user.findUnique({
        where: { id: userId },
        select: { targetWeight: true, targetDate: true, baselineRhr: true },
      }),
      prisma.dailyMetrics.findUnique({
        where: { userId_date: { userId, date } },
      }),
      prisma.dailyMetrics.findUnique({
        where: { userId_date: { userId, date: dayBefore } },
      }),
      prisma.activity.findMany({
        where: { userId, date },
        orderBy: { tss: "desc" },
      }),
      prisma.mealLog.findMany({
        where: { userId, date },
      }),
      // Constrained by `date` (not "latest in DB") so a summary generated
      // for a historical day reflects the user's weight as of that day.
      prisma.weightLog.findFirst({
        where: { userId, date: { lte: date } },
        orderBy: { date: "desc" },
      }),
      prisma.weightLog.findFirst({
        where: { userId, date: { lte: weekAgo } },
        orderBy: { date: "desc" },
      }),
    ]);

  if (!user) return null;
  return {
    summaryDate: date,
    user,
    today,
    yesterday,
    todayActivities,
    todayMealLogs,
    latestWeight,
    weightWeekAgo,
  };
}

export async function getOrGenerateDailySummary(
  userId: string,
  date: Date,
): Promise<DailySummary | null> {
  if (!isEnabled()) return null;

  const cached = await prisma.dailySummary.findUnique({
    where: { userId_date: { userId, date } },
  });
  if (cached) return cached;

  const input = await loadInput(userId, date);
  if (!input) return null;

  const summaryText = await callClaude(input);
  return prisma.dailySummary.upsert({
    where: { userId_date: { userId, date } },
    update: { summaryText, generatedAt: new Date() },
    create: { userId, date, summaryText },
  });
}

export async function regenerateDailySummary(
  userId: string,
  date: Date,
): Promise<DailySummary | null> {
  if (!isEnabled()) return null;

  const input = await loadInput(userId, date);
  if (!input) return null;

  const summaryText = await callClaude(input);
  return prisma.dailySummary.upsert({
    where: { userId_date: { userId, date } },
    update: { summaryText, generatedAt: new Date() },
    create: { userId, date, summaryText },
  });
}
