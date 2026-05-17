# Fitness Intelligence Model

> Decision engine spec for the AI coach layer of getmAIlean.
> Status: v1 draft — implementation-ready.

---

## 0. Design Philosophy

The app is not a dashboard with AI sprinkles. It is a coach with data-backed judgment. Every surface answers one of three questions:

- **Today** — what should I do right now, and why?
- **Trends** — what is actually changing, and does it matter?
- **Plan** — what am I building toward this week?

The decision engine is the code that answers "what should I do today" in a deterministic, testable way. Claude is used only for *copy generation* (translating a structured decision into natural language). The decision itself is pure logic.

---

## 1. Inputs

### 1.1 Available Today (from `DailyMetrics`, `Activity`, `WeightLog`, `MealLog`, `User`)

| Field | Source | Type | Notes |
|---|---|---|---|
| `ctl` | `DailyMetrics` | `Float` | Chronic Training Load (fitness) |
| `atl` | `DailyMetrics` | `Float` | Acute Training Load (fatigue) |
| `rampRate` | `DailyMetrics` | `Float` | CTL change rate (TSS/week) |
| `rhr` | `DailyMetrics` | `Int` | Resting heart rate (bpm) |
| `hrv` | `DailyMetrics` | `Float` | HRV (ms) |
| `sleepHours` | `DailyMetrics` | `Float` | Total sleep duration |
| `sleepScore` | `DailyMetrics` | `Int` | 0–100 sleep quality score |
| `steps` | `DailyMetrics` | `Int` | Daily step count |
| `kcalConsumed` | `DailyMetrics` | `Int` | Total calories consumed |
| `carbsGrams` | `DailyMetrics` | `Float` | Carbs (g) |
| `proteinGrams` | `DailyMetrics` | `Float` | Protein (g) |
| `fatGrams` | `DailyMetrics` | `Float` | Fat (g) |
| `baselineRhr` | `User` | `Int?` | User-level RHR baseline |
| `targetWeight` | `User` | `Float?` | Goal weight in kg |
| `targetDate` | `User` | `DateTime?` | Goal deadline |
| `weightKg` | `WeightLog` | `Float` | Daily weight entry |
| `mealType` / `status` | `MealLog` | `String` | breakfast / comida / merienda / cena, per day |
| `tss`, `durationMin`, `type` | `Activity` | mixed | Per-activity training stress score + type |

### 1.2 Derived at Decision Time

These are computed from the raw fields above; not stored separately in v1.

| Derived Signal | Computation |
|---|---|
| `rhrDelta` | `rhr - baselineRhr` (null if either missing) |
| `hrvBaseline7d` | Rolling 7-day mean HRV (requires 7 days of history) |
| `hrvDropPct` | `hrvBaseline7d > 0 ? (hrvBaseline7d - hrv) / hrvBaseline7d * 100 : 0` |
| `weightTrend7d` | `latestWeight - weight7dAgo` (kg/week) |
| `mealComplianceToday` | Count of meals where `status = "compliant"` / 4 |
| `mealComplianceWeek` | Mean daily compliance over the last 7 days |
| `daysSinceActivity` | Days since last `Activity` row |
| `tssPast7d` | Sum of `tss` for all activities in the past 7 days |
| `form` | `ctl - atl` (Training Stress Balance / TSB) |

### 1.3 Future Inputs (not in schema yet — label as `[FUTURE]` in code)

| Input | Why | Source Candidate |
|---|---|---|
| Subjective feel | 1–5 energy/mood check-in at app open | In-app form |
| Injury/soreness log | Overrides push recommendation | In-app form |
| Plan structure | Scheduled workout vs. spontaneous | Intervals.icu calendar |
| Body composition | % body fat, muscle mass | External scale via API |
| Menstrual cycle phase | Affects HRV/RHR interpretation | Manual or Apple Health |
| VO2 max trend | Fitness trajectory signal | Intervals.icu / Garmin |
| Nutrition targets | Per-meal macro goals | User profile extension |

### 1.4 Data Freshness & Confidence

```typescript
type DataFreshness = "fresh" | "stale" | "missing";

// A metric is "fresh" if its DailyMetrics row exists for today (UTC).
// "stale" if the most recent row is 1–3 days old.
// "missing" if > 3 days old or no row exists at all.
```

Confidence degrades as follows:

| Condition | Confidence Penalty | Effect |
|---|---|---|
| `today` DailyMetrics row missing | −65 pts | Recommendation caps at "data missing" |
| RHR missing | −10 pts | Cannot flag recovery |
| HRV missing | −10 pts | Cannot flag recovery |
| Sleep data missing | −5 pts | Sleep signal skipped |
| Weight not logged today | −5 pts | Weight signal skipped |
| No 7-day HRV baseline | −10 pts | HRV drop % unavailable |
| Sync stale > 1 day | −15 pts | Entire score suspect |

When confidence < 40, the recommendation **must** be `DATA_MISSING` regardless of other signals.

---

## 2. Thresholds

All thresholds are **assumptions** unless marked `[EVIDENCE]`. Assumptions are reasonable sports-science starting points and should be tuned per user over time.

### 2.1 Ramp Rate

Training load ramp — increase in CTL per week.

| Value | Status | Notes |
|---|---|---|
| ≤ +5 TSS/week | Green | Conservative build |
| +5 to +8 TSS/week | Yellow | Acceptable but monitor |
| +8 to +10 TSS/week | Orange | Borderline — watch recovery |
| > +10 TSS/week | Red | Injury risk zone [EVIDENCE: ~10% weekly load rule] |
| < −5 TSS/week | Yellow | Detraining; acceptable during taper |
| < −15 TSS/week | Orange | Significant detraining |

*Assumption: TSS/week proxy for load; actual CTL ramp rate stored in `rampRate` field.*

### 2.2 Resting Heart Rate vs. Baseline

`baselineRhr` is set by the user or computed as a 30-day rolling min.

| `rhrDelta` | Status |
|---|---|
| −5 to +4 bpm | Green |
| +5 to +7 bpm | Yellow — possible fatigue or illness |
| +8 to +11 bpm | Orange — likely overreached or sick |
| ≥ +12 bpm | Red — do not train; assess health |
| < −5 bpm | Green with note — possible good adaptation |

*Assumption: +5 bpm threshold common in athlete monitoring literature.*

### 2.3 HRV vs. Baseline (7-day rolling mean)

| `hrvDropPct` | Status |
|---|---|
| Drop < 10% | Green |
| Drop 10–19% | Yellow — elevated stress |
| Drop 20–29% | Orange — compromised recovery |
| Drop ≥ 30% | Red — full recovery day |
| No 7-day baseline yet | Unknown (treated as Yellow) |

*Assumption: % drop thresholds derived from HRV4Training guidelines.*

### 2.4 Sleep

| Condition | Status |
|---|---|
| ≥ 7.5h AND score ≥ 75 | Green |
| 6.5–7.4h OR score 60–74 | Yellow |
| 5.5–6.4h OR score 50–59 | Orange |
| < 5.5h OR score < 50 | Red |
| Missing | Unknown (treated as Yellow) |

*Assumption: 7h minimum from standard guidelines [EVIDENCE: NSF recommendations]. Score thresholds are device-agnostic estimates.*

### 2.5 Weight Trend

Context-dependent: green = trend toward goal.

| Condition | Direction | Status |
|---|---|---|
| Trend toward target at ≤ 0.5 kg/week | Cutting | Green |
| Trend away from target > 0.3 kg/week | Cutting | Yellow |
| No weight logged in > 3 days | Any | Yellow (incomplete signal) |
| Spike ≥ +1.5 kg in 24h after normal adherence | Any | Yellow (likely water/sodium) |
| Trend toward target at ≤ 0.3 kg/week | Gaining | Green |
| Gaining > 0.5 kg/week | Gaining | Yellow (too fast, likely fat) |

*Assumption: 0.5 kg/week cut rate from standard body recomp guidelines.*

### 2.6 Meal Adherence

"Compliant" = `MealLog.status === "compliant"`. Four meals per day: breakfast, comida, merienda, cena.

| `mealComplianceToday` | Status |
|---|---|
| 4/4 | Green |
| 3/4 | Yellow |
| 2/4 | Orange |
| ≤ 1/4 or no logs | Red |

7-day compliance average:

| Rolling 7-day avg | Status |
|---|---|
| ≥ 85% | Green |
| 70–84% | Yellow |
| 55–69% | Orange |
| < 55% | Red |

### 2.7 Training Recency / Load

| Condition | Status |
|---|---|
| Activity in last 24h | — (consider current TSS/fatigue) |
| 1–3 days since last activity | Green (normal rest) |
| 4–6 days since last activity | Yellow — check if intended |
| 7+ days since last activity | Red — unplanned detraining |
| TSS past 7 days = 0 (but user has a training history) | Red |

---

## 3. Scoring Model

### 3.1 Flag Aggregation

Each signal produces a severity level: `0=green`, `1=yellow`, `2=orange`, `3=red`.

```typescript
type Severity = 0 | 1 | 2 | 3;

type SignalFlags = {
  rampRate: Severity;
  rhr: Severity;
  hrv: Severity;
  sleep: Severity;
  weightTrend: Severity;
  mealCompliance: Severity;
  trainingRecency: Severity;
};
```

### 3.2 Score Computation

```typescript
const WEIGHTS: Record<keyof SignalFlags, number> = {
  rampRate:        3,  // injury risk: high weight
  rhr:             3,  // recovery: high weight
  hrv:             3,  // recovery: high weight
  sleep:           2,
  weightTrend:     1,
  mealCompliance:  1,
  trainingRecency: 2,
};

// Returns 0–100. Higher = more "green" / ready to train.
function computeReadinessScore(flags: SignalFlags): number {
  const MAX_SCORE = Object.values(WEIGHTS).reduce((a, b) => a + b, 0) * 3; // 45
  const rawPenalty = (Object.keys(flags) as Array<keyof SignalFlags>)
    .reduce((sum, k) => sum + flags[k] * WEIGHTS[k], 0);
  return Math.round(((MAX_SCORE - rawPenalty) / MAX_SCORE) * 100);
}
```

### 3.3 Red-Flag Override Rules

These bypass the score and force a specific recommendation regardless of score:

| Condition | Forced Recommendation |
|---|---|
| `rhrDelta >= 12` | `RECOVERY_CONTROLLED` |
| `hrvDropPct >= 30` | `RECOVERY_CONTROLLED` |
| `rampRate > 10` | `RECOVERY_CONTROLLED` |
| `confidence < 40` | `DATA_MISSING` |
| `syncStaleDays > 3` | `DATA_MISSING` |

### 3.4 Score → Recommendation Mapping

```typescript
type RecommendationCategory =
  | "RECOVERY_CONTROLLED"
  | "EASY_AEROBIC"
  | "NORMAL_TRAINING"
  | "PUSH_DAY"
  | "NUTRITION_FOCUS"
  | "DATA_MISSING";

function scoreToRecommendation(
  score: number,
  flags: SignalFlags,
  confidence: number,
): RecommendationCategory {
  if (confidence < 40) return "DATA_MISSING";

  // Override: any red flag in recovery domain → controlled rest
  if (flags.rhr === 3 || flags.hrv === 3 || flags.rampRate === 3) {
    return "RECOVERY_CONTROLLED";
  }

  // Nutrition focus: compliant training signal but poor adherence
  if (score >= 65 && flags.mealCompliance >= 2) {
    return "NUTRITION_FOCUS";
  }

  if (score >= 85) return "PUSH_DAY";
  if (score >= 65) return "NORMAL_TRAINING";
  if (score >= 45) return "EASY_AEROBIC";
  return "RECOVERY_CONTROLLED";
}
```

### 3.5 Confidence Computation

```typescript
function computeConfidence(input: DecisionInput): number {
  let score = 100;
  if (!input.todayMetrics) score -= 65;
  else {
    if (input.todayMetrics.rhr == null)        score -= 10;
    if (input.todayMetrics.hrv == null)        score -= 10;
    if (input.todayMetrics.sleepHours == null) score -= 5;
  }
  if (!input.latestWeight)           score -= 5;
  if (!input.hrv7dBaseline)          score -= 10;
  if (input.syncStaleDays > 1)       score -= 15;
  return Math.max(0, score);
}
```

---

## 4. Recommendation Categories

### 4.1 `RECOVERY_CONTROLLED`

**When:** Red flag in RHR, HRV, or ramp rate; OR score < 45.

**What it means:** The body needs real recovery. Not an easy ride. Rest, sleep, eat.

**Actions:**
- No structured training today
- Prioritize 8h sleep tonight
- Eat at or slightly above maintenance
- Hydrate, walk lightly if desired

### 4.2 `EASY_AEROBIC`

**When:** Score 45–64. Some yellow flags but no reds in recovery.

**What it means:** Body is managing but not primed. Easy movement supports recovery without digging deeper.

**Actions:**
- Zone 1–2 only (conversational pace)
- Cap at 60 min / 50 TSS
- No intervals, no strength
- Follow meal plan

### 4.3 `NORMAL_TRAINING`

**When:** Score 65–84.

**What it means:** All systems nominal. Execute the plan.

**Actions:**
- Follow scheduled workout
- Stick to nutrition targets
- Check in again tomorrow

### 4.4 `PUSH_DAY`

**When:** Score ≥ 85 AND no meal compliance flag.

**What it means:** Recovery is good, load is manageable, nutrition is on track. Rare green light.

**Actions:**
- Quality session, higher intensity OK
- Can extend duration or add intervals
- Front-load carbs
- Log everything — this is a data-rich day

### 4.5 `NUTRITION_FOCUS`

**When:** Score ≥ 65 (training-ready) BUT `mealComplianceToday ≤ 2/4` or `7-day compliance < 70%`.

**What it means:** Recovery is fine but the nutrition pattern is the limiting factor. Don't throw a good training day at a bad fuel situation.

**Actions:**
- Train if scheduled (short session OK)
- Primary focus: rebuild the eating pattern
- No aggressive deficit today

### 4.6 `DATA_MISSING`

**When:** Confidence < 40, or sync stale > 3 days, or today's DailyMetrics row is absent.

**What it means:** The coach doesn't have enough to make a call. Get the data first.

**Actions:**
- Check sync status in Admin panel
- Manually log weight / meals if sync is delayed
- Come back after data is fresh

---

## 5. Coach Copy Tone

### 5.1 Principles

- **Concise.** One recommendation + one reason. Not a paragraph.
- **Direct.** "Rest today" not "you might want to consider a rest day."
- **Human.** Second person. Conversational. No greeting, no "today you...".
- **No fake certainty.** Say "looks like" or "your data suggests" when signal is incomplete.
- **Explains why.** Always one "because" clause.
- **What to do.** End with a concrete action, not an observation.

### 5.2 Template Structure

```
[Signal summary] → [Recommendation] because [reason]. [Action].
```

### 5.3 Example Output Copy

**PUSH_DAY:**
> RHR is 2 below baseline, HRV is strong, and you've hit every meal this week — green light. Go hard today; front-load carbs and log the session.

**RECOVERY_CONTROLLED:**
> RHR is up 9 bpm and HRV dropped 28% from your baseline — your body is working harder than usual off the bike. Skip training today; sleep and eat are the session.

**EASY_AEROBIC:**
> Sleep came in at 5.9h last night and HRV is down slightly. You can move but keep it Zone 2 — 45 min max, no intervals.

**NUTRITION_FOCUS:**
> Recovery metrics look fine, but you've hit 2 of 4 meals three days running. Train short if you want, but the real work today is re-anchoring the eating pattern.

**DATA_MISSING:**
> Sync ran 4 days ago — not enough current data to make a call. Check the Admin panel and reconnect Intervals.icu, then come back.

**Weight spike (normal adherence):**
> Weight is up 1.7 kg since yesterday but meals were on point — likely water retention or sodium. Don't adjust calories yet; give it 2 days.

### 5.4 Copy Generation via Claude

The structured decision (category + signal flags + confidence) is passed to Claude with a tight system prompt. The model does *not* make the decision — it only converts the struct to natural language copy.

```typescript
type CoachDecision = {
  category: RecommendationCategory;
  score: number;
  confidence: number;
  flags: SignalFlags;
  signals: {
    rhrDelta: number | null;
    hrvDropPct: number | null;
    sleepHours: number | null;
    rampRate: number | null;
    mealComplianceToday: number; // 0–4
    daysSinceActivity: number | null;
  };
};
```

System prompt for copy generation (extends existing `SYSTEM_PROMPT` in `summarize.ts`):

```
You write a single coaching message based on a structured fitness decision. Output 1–3 sentences, second person, conversational. State the recommendation and the top reason why. End with one concrete action. No greeting, no "today you...", no markdown. Don't invent data not given. Use "looks like" or "your data suggests" when confidence < 70.
```

---

## 6. Edge Cases

### 6.1 Missing Sleep / HRV / RHR

- Missing sleep: skip sleep signal, deduct 5 confidence. Other signals still used.
- Missing HRV: skip HRV flag, deduct 10 confidence. If RHR also missing, recommendation cannot be stronger than `EASY_AEROBIC`.
- Missing RHR: same as above for RHR.
- Missing all three recovery signals: cap recommendation at `EASY_AEROBIC`, copy acknowledges incomplete data.

### 6.2 No Recent Activities

- `daysSinceActivity = 4–6`: flag Yellow, include in copy ("you haven't logged a session in 5 days — intentional rest or did something come up?").
- `daysSinceActivity >= 7`: flag Red. Override to `EASY_AEROBIC` minimum to encourage re-engagement, not `PUSH_DAY`.

### 6.3 Weight Spike After Normal Adherence

- `weightTrend24h >= +1.5 kg` AND `mealComplianceToday >= 3/4`: treat as water retention.
- **Do not** flag Red for nutrition. Flag Yellow with water-retention note in copy.
- Do not adjust calorie recommendation downward.

### 6.4 High Ramp But User Feels Good

- Ramp > 10 TSS/week forces `RECOVERY_CONTROLLED` regardless of other signals.
- Subjective feel (`[FUTURE]`) will soften this to `EASY_AEROBIC` in v2, not fully override it.
- Copy acknowledges the tension: "Your load ramp is above threshold even though recovery looks OK — better to back off now than after the injury."

### 6.5 Low Adherence But Good Recovery

- `mealCompliance <= 2/4` BUT `score >= 65`: → `NUTRITION_FOCUS`.
- Training is not forbidden; copy emphasizes nutrition as the bottleneck.
- Don't penalize readiness score for meal compliance beyond the `NUTRITION_FOCUS` redirect.

### 6.6 Stale Sync Data

- `syncStaleDays > 3`: → `DATA_MISSING`. No training recommendation possible.
- `syncStaleDays 1–3`: Yellow confidence penalty. Recommendation includes a note: "Data from [N] days ago — may not reflect today's state."
- `syncStaleDays = 0`: Fresh.

---

## 7. Tests

### 7.1 Unit Test Scenarios for `computeReadiness`

File: `web/lib/ai/__tests__/decision.test.ts`

```typescript
describe("scoreToRecommendation", () => {
  it("returns PUSH_DAY when all signals are green", () => {
    const flags: SignalFlags = {
      rampRate: 0, rhr: 0, hrv: 0,
      sleep: 0, weightTrend: 0,
      mealCompliance: 0, trainingRecency: 0,
    };
    expect(scoreToRecommendation(computeReadinessScore(flags), flags, 100))
      .toBe("PUSH_DAY");
  });

  it("returns RECOVERY_CONTROLLED when rhrDelta >= 12 (override)", () => {
    const flags: SignalFlags = {
      rampRate: 0, rhr: 3, hrv: 0,
      sleep: 1, weightTrend: 0,
      mealCompliance: 0, trainingRecency: 0,
    };
    expect(scoreToRecommendation(computeReadinessScore(flags), flags, 90))
      .toBe("RECOVERY_CONTROLLED");
  });

  it("returns DATA_MISSING when confidence < 40", () => {
    const flags: SignalFlags = {
      rampRate: 0, rhr: 0, hrv: 0,
      sleep: 0, weightTrend: 0,
      mealCompliance: 0, trainingRecency: 0,
    };
    expect(scoreToRecommendation(100, flags, 35))
      .toBe("DATA_MISSING");
  });

  it("returns NUTRITION_FOCUS when score >= 65 but meal compliance is orange", () => {
    const flags: SignalFlags = {
      rampRate: 0, rhr: 0, hrv: 0,
      sleep: 0, weightTrend: 0,
      mealCompliance: 2, trainingRecency: 0,
    };
    const score = computeReadinessScore(flags);
    expect(score).toBeGreaterThanOrEqual(65);
    expect(scoreToRecommendation(score, flags, 90))
      .toBe("NUTRITION_FOCUS");
  });

  it("returns EASY_AEROBIC when score is 45–64", () => {
    const flags: SignalFlags = {
      rampRate: 1, rhr: 1, hrv: 1,
      sleep: 1, weightTrend: 1,
      mealCompliance: 1, trainingRecency: 1,
    };
    const score = computeReadinessScore(flags);
    expect(score).toBeGreaterThanOrEqual(45);
    expect(score).toBeLessThan(65);
    expect(scoreToRecommendation(score, flags, 80))
      .toBe("EASY_AEROBIC");
  });
});

describe("computeConfidence", () => {
  it("returns 100 when all data is present and sync is fresh", () => {
    expect(computeConfidence(fullFreshInput)).toBe(100);
  });

  it("returns <= 40 when DailyMetrics row is missing and sync is stale", () => {
    const input = { ...fullFreshInput, todayMetrics: null, syncStaleDays: 2 };
    expect(computeConfidence(input)).toBeLessThanOrEqual(40);
  });

  it("penalizes missing HRV and RHR independently", () => {
    const withHrv = computeConfidence({ ...fullFreshInput, todayMetrics: { ...metrics, hrv: null } });
    const withRhr = computeConfidence({ ...fullFreshInput, todayMetrics: { ...metrics, rhr: null } });
    expect(withHrv).toBe(90);
    expect(withRhr).toBe(90);
  });
});
```

### 7.2 Threshold Tests

```typescript
describe("rhrToSeverity", () => {
  it.each([
    [4, 0],   // green
    [5, 1],   // yellow
    [8, 2],   // orange
    [12, 3],  // red
  ])("rhrDelta=%i → severity %i", (delta, expected) => {
    expect(rhrToSeverity(delta)).toBe(expected);
  });
});

describe("rampRateToSeverity", () => {
  it.each([
    [5, 0],
    [8, 1],
    [10, 2],
    [11, 3],
  ])("rampRate=%i → severity %i", (rate, expected) => {
    expect(rampRateToSeverity(rate)).toBe(expected);
  });
});
```

### 7.3 Edge Case Tests

```typescript
describe("edge cases", () => {
  it("weight spike after normal adherence → not Red nutrition flag", () => {
    const flags = computeFlags({
      ...baseInput,
      weightTrend24h: 1.8,
      mealComplianceToday: 4,
    });
    expect(flags.weightTrend).toBeLessThan(3);
  });

  it("no recent activities for 7 days → trainingRecency is Red", () => {
    const flags = computeFlags({ ...baseInput, daysSinceActivity: 7 });
    expect(flags.trainingRecency).toBe(3);
  });

  it("all recovery signals missing → confidence < 60", () => {
    const conf = computeConfidence({
      ...baseInput,
      todayMetrics: { ...metrics, rhr: null, hrv: null, sleepHours: null },
    });
    expect(conf).toBeLessThan(60);
  });

  it("stale sync > 3 days → DATA_MISSING regardless of flags", () => {
    const result = makeDecision({ ...baseInput, syncStaleDays: 4 });
    expect(result.category).toBe("DATA_MISSING");
  });
});
```

### 7.4 Copy Snapshot Tests

Once copy generation is wired up, add snapshot tests for each `RecommendationCategory`:

```typescript
describe("copy generation", () => {
  it("PUSH_DAY snapshot", async () => {
    const copy = await generateCoachCopy(pushDayDecision);
    expect(copy).toMatchSnapshot();
  });
  // ... one per category
});
```

Note: snapshot tests for LLM output should be treated as soft assertions — regenerate deliberately, not on every diff.

---

## 8. Architecture Notes

### 8.1 Where This Lives

```
web/lib/ai/
  summarize.ts          ← existing Claude summary (free text)
  decision.ts           ← NEW: rule engine (pure functions, no Claude)
  coach.ts              ← NEW: CoachDecision → Claude copy
  __tests__/
    decision.test.ts    ← NEW: unit tests for rule engine
    coach.test.ts       ← NEW: snapshot tests for copy
```

### 8.2 Decision vs. Summary

The existing `summarize.ts` generates free-text summaries by passing raw data directly to Claude. The new decision engine **decouples** the judgment from the language:

1. `decision.ts` → deterministic `CoachDecision` struct (no AI)
2. `coach.ts` → passes struct to Claude → natural language copy

This makes the decision logic testable, auditable, and improvable without touching the LLM layer.

### 8.3 Caching

`CoachDecision` structs should be cached per `(userId, date)` alongside `DailySummary`. Avoid recomputing on every page load.

---

## 9. Open Questions / v1 Assumptions

- [ ] Is `rampRate` in `DailyMetrics` already in TSS/week units, or per-day? **Assume per-week** — verify against Intervals.icu sync.
- [ ] Does HRV from Intervals.icu represent morning HRV or overnight? **Assume morning** — affects interpretation.
- [ ] Four meals (breakfast/comida/merienda/cena) — is this fixed or user-configurable? **Assume fixed for v1**.
- [ ] `baselineRhr` is user-set; should the app auto-compute from rolling 30-day min? **Auto-compute in v2**.
- [ ] What happens for users without a `targetWeight`? **Skip weight trend signal; reduce max confidence by 5**.
