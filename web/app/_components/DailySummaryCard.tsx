import type { DailySummary } from "@prisma/client";
import { getOrGenerateDailySummary, isEnabled } from "@/lib/ai/summarize";
import { regenerateSummaryAction } from "../actions/summary";

type Props = {
  userId: string;
  date: Date;
};

type LoadedSummary = {
  summary: DailySummary | null;
  error: string | null;
  generatedRelative: string | null;
};

function relativeFromNow(date: Date, nowMs: number): string {
  const min = Math.round((nowMs - date.getTime()) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

// Pre-compute the Date.now()-dependent "X ago" string here so the
// component render stays pure under React 19's react-hooks/purity rule.
async function loadSummary(userId: string, date: Date): Promise<LoadedSummary> {
  try {
    const summary = await getOrGenerateDailySummary(userId, date);
    if (!summary) return { summary: null, error: null, generatedRelative: null };
    return {
      summary,
      error: null,
      generatedRelative: relativeFromNow(summary.generatedAt, Date.now()),
    };
  } catch (err) {
    console.error("[DailySummaryCard] generation failed:", err);
    return {
      summary: null,
      error: "Couldn't generate summary — try refresh.",
      generatedRelative: null,
    };
  }
}

export async function DailySummaryCard({ userId, date }: Props) {
  if (!isEnabled()) return null;

  const { summary, error, generatedRelative } = await loadSummary(userId, date);

  return (
    <section className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400">
          Summary
        </h2>
        <form action={regenerateSummaryAction.bind(null, userId)}>
          <button
            type="submit"
            className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            Refresh
          </button>
        </form>
      </div>
      {summary ? (
        <>
          <p className="text-sm leading-relaxed">{summary.summaryText}</p>
          {generatedRelative ? (
            <p className="text-xs text-gray-500 dark:text-gray-400 tabular-nums">
              {generatedRelative}
            </p>
          ) : null}
        </>
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No data yet.
        </p>
      )}
    </section>
  );
}
