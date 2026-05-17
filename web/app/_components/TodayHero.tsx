import type { TodayBundle } from "@/lib/queries/today";
import { buildCoachInput, computeCoachDecision } from "@/lib/coach/rules";
import type { RecommendationCategory, DataQuality } from "@/lib/coach/rules";
import { BADGE_LABELS, DATA_LABEL, QUALITY_LABEL } from "@/lib/coach/copy";
import { Card, CardContent } from "./ui/card";
import { cn } from "@/lib/utils";

const BADGE_STYLES: Record<RecommendationCategory, string> = {
  "recovery": "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  "controlled-recovery": "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  "caution": "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  "steady": "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  "missing-data": "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

const HERO_BORDER: Record<RecommendationCategory, string> = {
  "recovery": "border-l-rose-500",
  "controlled-recovery": "border-l-amber-500",
  "caution": "border-l-yellow-500",
  "steady": "border-l-emerald-500",
  "missing-data": "border-l-slate-400",
};

const QUALITY_STYLES: Record<DataQuality, string> = {
  sufficient: "text-emerald-600 dark:text-emerald-400",
  partial: "text-amber-600 dark:text-amber-400",
  insufficient: "text-slate-500 dark:text-slate-400",
};

type Props = {
  bundle: TodayBundle;
};

export function TodayHero({ bundle }: Props) {
  const input = buildCoachInput(bundle);
  const decision = computeCoachDecision(input);

  return (
    <Card className={cn("border-l-4", HERO_BORDER[decision.category])}>
      <CardContent className="pt-6 space-y-5">
        {/* Category badge + title */}
        <div className="space-y-2">
          <span
            className={cn(
              "inline-block text-xs font-medium px-2.5 py-0.5 rounded-full",
              BADGE_STYLES[decision.category],
            )}
          >
            {BADGE_LABELS[decision.category]}
          </span>
          <h2 className="text-2xl font-semibold leading-snug">{decision.title}</h2>
        </div>

        {/* Why */}
        {decision.why.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
              Why
            </h3>
            <ul className="space-y-1">
              {decision.why.map((reason, index) => (
                <li key={`${reason}-${index}`} className="text-sm flex gap-2">
                  <span className="text-gray-400 dark:text-gray-500 shrink-0">•</span>
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Action checklist */}
        <div>
          <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">
            What to do
          </h3>
          <ul className="space-y-1.5">
            {decision.doItems.map((item, index) => (
              <li key={`${item}-${index}`} className="text-sm flex gap-2">
                <span className="text-gray-400 dark:text-gray-500 shrink-0 mt-0.5">—</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Watch for */}
        <div className="border-t pt-4">
          <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
            Watch for
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-300">{decision.watch}</p>
        </div>

        {/* Data confidence slot — accepts richer score from issue #31 without rework */}
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-gray-400 dark:text-gray-500">{DATA_LABEL}</span>
          <span className={QUALITY_STYLES[decision.dataQuality]}>
            {QUALITY_LABEL[decision.dataQuality]}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
