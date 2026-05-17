import type { RecommendationCategory, DataQuality } from "./rules";

export const COACH_TITLES: Record<RecommendationCategory, string> = {
  "recovery": "Take a full recovery day.",
  "controlled-recovery": "Take a controlled recovery day.",
  "caution": "Keep intensity low today.",
  "steady": "Good day for steady training.",
  "missing-data": "Not enough data to make a call.",
};

export const COACH_DO_ITEMS: Record<RecommendationCategory, string[]> = {
  "recovery": [
    "Rest or a short easy walk",
    "Focus on hitting protein targets",
    "Keep meals simple and consistent",
    "Prioritise an early night",
    "No structured training today",
  ],
  "controlled-recovery": [
    "30–45 min Zone 2 or walk, keep it conversational",
    "Hit protein targets",
    "Keep meals simple",
    "No intensity today",
  ],
  "caution": [
    "Zone 1–2 only if training, no intervals",
    "Cap effort at RPE 6/10",
    "Hit nutrition targets",
    "Prioritise sleep tonight",
  ],
  "steady": [
    "Follow your planned session as normal",
    "Hit carb and protein targets around training",
    "Check in with how you feel after warm-up",
  ],
  "missing-data": [
    "Default to moderate effort until data syncs",
    "Log your weight and meals to improve signal quality",
    "Sync your devices if you haven't already",
  ],
};

export const COACH_WATCH_NOTES: Record<RecommendationCategory, string> = {
  "recovery": "Resume normal training when sleep and HRV normalise.",
  "controlled-recovery": "If HRV rebounds tomorrow, resume normal training.",
  "caution": "If you feel strong after warm-up, it's fine to extend easy effort.",
  "steady": "Watch ramp rate if load has been building this week.",
  "missing-data": "Sync your devices to get a clearer picture.",
};

export const BADGE_LABELS: Record<RecommendationCategory, string> = {
  "recovery": "recovery",
  "controlled-recovery": "controlled recovery",
  "caution": "caution",
  "steady": "steady",
  "missing-data": "needs data",
};

export const QUALITY_LABEL: Record<DataQuality, string> = {
  sufficient: "All key data present",
  partial: "Partial data — lower confidence",
  insufficient: "Insufficient data",
};

export const DATA_LABEL = "Data:";
