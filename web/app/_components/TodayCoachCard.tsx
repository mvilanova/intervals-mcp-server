import type { TodayBundle } from "@/lib/queries/today";
import { buildCoachInput, computeCoachDecision } from "@/lib/coach/rules";
import type { RecommendationCategory } from "@/lib/coach/rules";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { cn } from "@/lib/utils";

const BADGE_STYLES: Record<RecommendationCategory, string> = {
  "recovery": "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  "controlled-recovery": "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  "caution": "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  "steady": "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  "missing-data": "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

const BADGE_LABELS: Record<RecommendationCategory, string> = {
  "recovery": "recovery",
  "controlled-recovery": "controlled recovery",
  "caution": "caution",
  "steady": "steady",
  "missing-data": "needs data",
};

type Props = {
  bundle: TodayBundle;
};

export function TodayCoachCard({ bundle }: Props) {
  const input = buildCoachInput(bundle);
  const decision = computeCoachDecision(input);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Today&apos;s recommendation</CardTitle>
          <span
            className={cn(
              "shrink-0 text-xs font-medium px-2 py-0.5 rounded-full",
              BADGE_STYLES[decision.category],
            )}
          >
            {BADGE_LABELS[decision.category]}
          </span>
        </div>
        {decision.dataQuality === "partial" && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Some metrics are missing — confidence is lower than usual.
          </p>
        )}
      </CardHeader>

      <CardContent className="space-y-4">
        <p className="text-lg font-semibold">{decision.title}</p>

        {decision.why.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">
              Why
            </h3>
            <ul className="space-y-0.5">
              {decision.why.map((reason, index) => (
                <li key={`${reason}-${index}`} className="text-sm flex gap-2">
                  <span className="text-gray-400 dark:text-gray-500 shrink-0">•</span>
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">
            Do
          </h3>
          <ul className="space-y-1">
            {decision.doItems.map((item, index) => (
              <li key={`${item}-${index}`} className="text-sm flex gap-2">
                <span className="text-gray-400 dark:text-gray-500 shrink-0 mt-0.5">—</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="border-t pt-3">
          <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
            Watch
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-300">{decision.watch}</p>
        </div>
      </CardContent>
    </Card>
  );
}
