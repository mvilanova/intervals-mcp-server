import type { DailySummary } from "@prisma/client";
import { getOrGenerateDailySummary, isEnabled } from "@/lib/ai/summarize";
import { regenerateSummaryAction } from "../actions/summary";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

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
    <Card>
      <CardHeader className="flex-row items-baseline justify-between space-y-0 gap-3">
        <CardTitle>Summary</CardTitle>
        <form action={regenerateSummaryAction.bind(null, userId)}>
          <Button type="submit" variant="ghost" size="sm">
            Refresh
          </Button>
        </form>
      </CardHeader>
      <CardContent className="space-y-3">
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
      </CardContent>
    </Card>
  );
}
