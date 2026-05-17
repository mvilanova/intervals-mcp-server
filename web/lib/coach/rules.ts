import type { TodayBundle } from "@/lib/queries/today";
import { COACH_DO_ITEMS, COACH_TITLES, COACH_WATCH_NOTES } from "./copy";

export type RecommendationCategory =
  | "recovery"
  | "controlled-recovery"
  | "caution"
  | "steady"
  | "missing-data";

export type DataQuality = "sufficient" | "partial" | "insufficient";

export interface CoachInput {
  rampRate: number | null;
  hrv: number | null;
  rhr: number | null;
  baselineRhr: number | null;
  sleepHours: number | null;
  sleepScore: number | null;
  yesterdayHrv: number | null;
}

export interface CoachDecision {
  category: RecommendationCategory;
  title: string;
  why: string[];
  doItems: string[];
  watch: string;
  dataQuality: DataQuality;
}

export function buildCoachInput(bundle: TodayBundle): CoachInput {
  return {
    rampRate: bundle.today?.rampRate ?? null,
    hrv: bundle.today?.hrv ?? null,
    rhr: bundle.today?.rhr ?? null,
    baselineRhr: bundle.user.baselineRhr,
    sleepHours: bundle.today?.sleepHours ?? null,
    sleepScore: bundle.today?.sleepScore ?? null,
    yesterdayHrv: bundle.yesterday?.hrv ?? null,
  };
}

type Signal = { score: number; reason: string };

function collectSignals(input: CoachInput): Signal[] {
  const signals: Signal[] = [];

  if (input.rampRate != null) {
    if (input.rampRate > 8) {
      signals.push({ score: 4, reason: "Training load is rising very steeply." });
    } else if (input.rampRate > 5) {
      signals.push({ score: 2, reason: "Ramp rate is high." });
    } else if (input.rampRate > 3) {
      signals.push({ score: 1, reason: "Training load has been building." });
    }
  }

  if (input.sleepHours != null) {
    if (input.sleepHours < 5.5) {
      signals.push({ score: 4, reason: "Sleep was very short last night." });
    } else if (input.sleepHours < 6.5) {
      signals.push({ score: 2, reason: "Sleep is below baseline." });
    } else if (input.sleepHours < 7) {
      signals.push({ score: 1, reason: "Sleep was slightly short." });
    }
  }

  if (input.sleepScore != null) {
    if (input.sleepScore < 55) {
      signals.push({ score: 2, reason: "Sleep quality was poor." });
    } else if (input.sleepScore < 65) {
      signals.push({ score: 1, reason: "Sleep quality was below average." });
    }
  }

  if (input.rhr != null && input.baselineRhr != null) {
    const delta = input.rhr - input.baselineRhr;
    if (delta > 7) {
      signals.push({ score: 2, reason: "Resting heart rate is well above your baseline." });
    } else if (delta > 4) {
      signals.push({ score: 1, reason: "Resting heart rate is elevated." });
    }
  }

  if (input.hrv != null && input.yesterdayHrv != null && input.yesterdayHrv > 0) {
    const ratio = input.hrv / input.yesterdayHrv;
    if (ratio < 0.75) {
      signals.push({ score: 2, reason: "HRV is significantly suppressed." });
    } else if (ratio < 0.9) {
      signals.push({ score: 1, reason: "HRV is slightly suppressed." });
    }
  }

  return signals;
}

function assessDataQuality(input: CoachInput): DataQuality {
  const hasRamp = input.rampRate != null;
  const hasSleep = input.sleepHours != null || input.sleepScore != null;

  // Primary signals (ramp rate + sleep) anchor the recommendation.
  // Secondary signals (HRV, RHR) only modify it — insufficient without the primaries.
  if (!hasRamp && !hasSleep) return "insufficient";
  if (!hasRamp || !hasSleep) return "partial";
  return "sufficient";
}

export function computeCoachDecision(input: CoachInput): CoachDecision {
  const dataQuality = assessDataQuality(input);

  if (dataQuality === "insufficient") {
    return {
      category: "missing-data",
      title: COACH_TITLES["missing-data"],
      why: ["Key metrics are not available yet."],
      doItems: COACH_DO_ITEMS["missing-data"],
      watch: COACH_WATCH_NOTES["missing-data"],
      dataQuality,
    };
  }

  const signals = collectSignals(input);
  const totalScore = signals.reduce((acc, s) => acc + s.score, 0);

  let category: RecommendationCategory;
  if (totalScore >= 4) {
    category = "recovery";
  } else if (totalScore >= 2) {
    category = "controlled-recovery";
  } else if (totalScore >= 1) {
    category = "caution";
  } else {
    category = "steady";
  }

  return {
    category,
    title: COACH_TITLES[category],
    why: signals.length > 0 ? signals.map((s) => s.reason) : ["All metrics look normal."],
    doItems: COACH_DO_ITEMS[category],
    watch: COACH_WATCH_NOTES[category],
    dataQuality,
  };
}
