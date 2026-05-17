# Fitness Intelligence Roadmap — GitHub Issue Drafts

Ready-to-copy issue drafts. Paste into GitHub Issues or create via `gh issue create`.

---

## Issue 1: AI coach decision layer v1

**Title:** `feat(ai): implement coach decision engine (rule-based readiness score)`

**Labels:** `feature`, `ai`, `backend`

**Body:**

### Summary

Implement the deterministic rule engine defined in `docs/fitness-intelligence-model.md`. This separates the judgment layer from Claude — the decision is pure TypeScript logic; Claude only writes the copy.

### What to build

- `web/lib/ai/decision.ts` — exports:
  - `computeFlags(input: DecisionInput): SignalFlags`
  - `computeReadinessScore(flags: SignalFlags): number`
  - `computeConfidence(input: DecisionInput): number`
  - `makeDecision(input: DecisionInput): CoachDecision`
- `web/lib/ai/coach.ts` — exports:
  - `generateCoachCopy(decision: CoachDecision): Promise<string>` (calls Claude)
- Types: `CoachDecision`, `SignalFlags`, `RecommendationCategory`, `DecisionInput`

### Thresholds to implement

See `docs/fitness-intelligence-model.md` §2 for all threshold tables (ramp rate, RHR delta, HRV drop %, sleep, weight trend, meal compliance, training recency).

### Acceptance Criteria

- [ ] `makeDecision()` returns correct `RecommendationCategory` for all 6 categories
- [ ] Red-flag overrides bypass the score (RHR ≥ +12, HRV drop ≥ 30%, ramp > 10)
- [ ] `DATA_MISSING` returned when confidence < 40
- [ ] `generateCoachCopy()` passes `CoachDecision` struct to Claude (does not pass raw data)
- [ ] All inputs typed; no `any`
- [ ] Unit tests pass (see §7 of spec for test scenarios)

### Dependencies

None — this is the foundation for all other AI features.

---

## Issue 2: Daily recommendation engine tests

**Title:** `test(ai): unit + snapshot tests for decision engine and coach copy`

**Labels:** `test`, `ai`

**Body:**

### Summary

Add comprehensive tests for the decision engine implemented in Issue 1. Tests must be deterministic (decision layer) and snapshot-based (copy layer).

### What to build

- `web/lib/ai/__tests__/decision.test.ts`
  - All threshold boundary tests (see spec §7.2)
  - All edge cases (see spec §7.3)
  - Score/recommendation mapping for each band
  - Confidence computation with various missing-data combinations
- `web/lib/ai/__tests__/coach.test.ts`
  - One snapshot per `RecommendationCategory` (6 total)
  - Tests that the correct `CoachDecision` struct is passed to Claude (mock Anthropic SDK)
  - Snapshot update policy documented in test file header

### Acceptance Criteria

- [ ] `vitest` test suite passes (`npm test` in `web/`)
- [ ] 100% branch coverage on `decision.ts`
- [ ] Snapshot tests exist for all 6 recommendation categories
- [ ] Anthropic SDK is mocked in tests (no live API calls in CI)
- [ ] Edge cases covered: missing sleep, missing HRV, stale sync, weight spike, high ramp + good recovery, low adherence + good recovery

### Dependencies

- Issue 1 (decision engine must exist)

---

## Issue 3: Data quality confidence model

**Title:** `feat(ai): data confidence scoring and staleness detection`

**Labels:** `feature`, `ai`, `data-quality`

**Body:**

### Summary

Today the app shows `—` when data is missing. The confidence model formalises missing/stale data into a score that the decision engine uses to degrade or block recommendations.

### What to build

- Extend `computeConfidence()` (from Issue 1) with staleness checks sourced from `SyncSourceRun`
- `web/lib/ai/confidence.ts` — exports:
  - `getDataFreshness(userId: string, date: Date): Promise<DataFreshnessReport>`
  - `DataFreshnessReport` type: per-signal freshness status + `syncStaleDays`
- Surface confidence score on the Today page — small badge or tooltip on the DailySummaryCard
- When confidence < 70: copy includes a note about incomplete data

### Schema changes

None required — uses existing `SyncSourceRun` and `DailyMetrics` tables.

### Acceptance Criteria

- [ ] `getDataFreshness()` correctly computes staleness per signal source
- [ ] `syncStaleDays` is derived from last successful `SyncSourceRun` for the wellness source
- [ ] Confidence < 40 → `DATA_MISSING` recommendation (enforced at decision layer)
- [ ] Confidence 40–70 → recommendation shown with "partial data" note in copy
- [ ] Confidence is visible to the user (not just used internally)
- [ ] Tests for all staleness scenarios

### Dependencies

- Issue 1 (confidence is consumed by the decision engine)

---

## Issue 4: Personalization / coach memory

**Title:** `feat(coach): persistent user profile for personalized recommendations`

**Labels:** `feature`, `personalization`, `backend`

**Body:**

### Summary

The coach needs persistent knowledge about the user: goals, injuries, training constraints, past failures, food preferences, and what the user has already been told. This is the "Coach Memory" surface from the product spec.

### What to build

**Schema additions:**

```prisma
model CoachProfile {
  id           String   @id @default(cuid())
  userId       String   @unique
  user         User     @relation(...)
  goals        Json     // { primaryGoal, targetEvents, horizon }
  injuries     Json[]   // [{ area, severity, since, notes }]
  constraints  Json     // { maxHoursPerWeek, preferredDays, equipment }
  preferences  Json     // { cuisines, excludedFoods, mealStructure }
  pastFailures Json[]   // [{ period, what, why }]
  updatedAt    DateTime @updatedAt
}
```

**UI:**
- New `/coach-memory` route — read-only view of what the app knows
- Editable fields: goals, injuries, constraints, preferences
- "Past failures" section populated by the app over time (not user-entered)

**Decision engine integration:**
- Pass relevant profile fields to `makeDecision()` as context
- Injuries → can veto `PUSH_DAY` for affected movement types
- Goal horizon → adjusts acceptable ramp rate (peaking vs. base-building)

### Acceptance Criteria

- [ ] `CoachProfile` schema migrated and seeded
- [ ] `/coach-memory` page renders all profile sections
- [ ] At least goals and injuries are editable via the UI
- [ ] `makeDecision()` accepts optional `CoachProfile` context
- [ ] An active injury of severity `high` downgrades `PUSH_DAY` → `NORMAL_TRAINING`

### Dependencies

- Issue 1 (decision engine must accept profile context)

---

## Issue 5: Feedback loop / subjective check-ins

**Title:** `feat(coach): daily subjective check-in (energy, mood, soreness)`

**Labels:** `feature`, `ux`, `personalization`

**Body:**

### Summary

Objective data (HRV, RHR, sleep) tells half the story. A 10-second check-in at app open captures the user's felt state and can override or confirm what the data says — making recommendations both more accurate and more trusted.

### What to build

**Schema additions:**

```prisma
model SubjectiveCheckin {
  id        String   @id @default(cuid())
  userId    String
  date      DateTime @db.Date
  energy    Int      // 1–5
  mood      Int      // 1–5
  soreness  Int      // 1–5 (1=none, 5=severe)
  notes     String?
  user      User     @relation(...)

  @@unique([userId, date])
}
```

**UI:**
- Compact check-in widget on Today page (appears if not yet filled for today)
- 3 emoji sliders: energy / mood / soreness
- Optional free-text note (max 140 chars)
- Dismissible — not blocking

**Decision engine integration:**
- `energy <= 2` → same effect as Yellow sleep signal (additive)
- `soreness >= 4` → vetoes `PUSH_DAY`; copy acknowledges soreness
- `energy >= 4` AND high ramp rate → allows `EASY_AEROBIC` instead of forced `RECOVERY_CONTROLLED` (softens but does not override the override)
- Pass `SubjectiveCheckin` to `makeDecision()` as optional override context

### Acceptance Criteria

- [ ] Check-in widget visible and functional on Today page
- [ ] Data persists to `SubjectiveCheckin` table
- [ ] Decision engine uses `energy` and `soreness` when check-in exists
- [ ] High ramp + good subjective feel → `EASY_AEROBIC` (not full `RECOVERY_CONTROLLED`)
- [ ] Missing check-in does not degrade confidence (it is supplemental, not required)
- [ ] Tests for all subjective override scenarios

### Dependencies

- Issue 1 (decision engine must accept check-in context)

---

## Issue 6: Plan adjustment logic

**Title:** `feat(plan): weekly training plan with dynamic load adjustment`

**Labels:** `feature`, `planning`, `backend`

**Body:**

### Summary

The "Plan" surface shows the weekly training structure and adjusts targets based on actual performance. This moves the app from reactive (what happened today) to proactive (what should the week look like).

### What to build

**Schema additions:**

```prisma
model WeeklyPlan {
  id           String   @id @default(cuid())
  userId       String
  weekStart    DateTime @db.Date  // Monday UTC
  targetTss    Float    // target weekly TSS
  targetDays   Json     // [{ day: "Mon", intent: "easy" | "quality" | "rest" }]
  nutritionFocus String? // "cut" | "maintain" | "fuel"
  notes        String?
  user         User     @relation(...)

  @@unique([userId, weekStart])
}
```

**Logic:**
- Auto-generate `WeeklyPlan` at week start based on:
  - Current CTL and target CTL trajectory
  - Ramp rate ceiling (≤ 8 TSS/week safe zone)
  - Remaining days to `targetDate`
- If actual TSS for week-to-date is ≥ 20% below plan by Wednesday → copy notes the shortfall
- If actual TSS ≥ 15% above plan by Friday → suggest scaling back the weekend

**UI:**
- `/plan` route: weekly calendar with daily intent labels + actual vs. planned TSS
- Nutrition focus badge for the week

### Acceptance Criteria

- [ ] `WeeklyPlan` auto-generated each Monday (or on first login of the week)
- [ ] Weekly TSS target derived from CTL trajectory, not arbitrary
- [ ] Mid-week shortfall and overshoot detections work correctly
- [ ] `/plan` page renders correctly on mobile
- [ ] Plan adjustments shown in the Today recommendation when relevant

### Dependencies

- Issue 1 (decision engine used for daily intent labels)
- Issue 4 (coach profile provides goal horizon and constraints)

---

## Issue 7: Trend explanations

**Title:** `feat(trends): intelligent trend surface with signal explanations`

**Labels:** `feature`, `ux`, `ai`

**Body:**

### Summary

The "Trends" surface should not just graph everything — it should explain what's changing and whether it matters. Graphing weight without context is noise; graphing weight + adherence + the explanation is signal.

### What to build

**Metrics to trend (30-day rolling window):**
- Weight trajectory vs. target pace
- CTL/ATL/TSB (training load balance)
- HRV 7-day rolling mean + trend direction
- RHR 7-day rolling mean + trend direction
- Sleep hours + score rolling mean
- Weekly meal compliance %

**Explanation layer:**
- Each trend card includes a one-sentence "what this means" beneath the chart
- Generated from a structured diff (is this improving, stable, or declining?) — not free-text Claude output
- Examples:
  - Weight: "Down 0.8 kg this week — on pace to reach target 3 days early."
  - CTL: "Fitness trending up, fatigue is ahead of it — performance will return after your easy week."
  - HRV: "HRV has been declining 5 days in a row — recovery may be falling behind load."

**Implementation:**
- `web/lib/trends/explain.ts` — deterministic explanation strings based on 7-day and 30-day deltas
- Not Claude-generated (no latency, no cost, fully testable)
- Claude used only for summaries that require multi-signal synthesis

### Acceptance Criteria

- [ ] `/trends` route exists with all 6 metric trend lines
- [ ] Each chart has a static explanation string generated by `explain.ts`
- [ ] Explanation correctly identifies direction (up/down/flat) and whether it's good/bad in context
- [ ] Trend page is useful with 7 days of data; labels correctly when < 7 days available
- [ ] Tests for `explain.ts` covering all direction × goal combinations

### Dependencies

- Issue 3 (confidence / staleness needed to grey out stale trend data)

---

## Issue 8: Admin / Data Health improvements

**Title:** `feat(admin): data health dashboard with actionable sync diagnostics`

**Labels:** `feature`, `admin`, `data-quality`

**Body:**

### Summary

The existing `/admin/sync` page shows sync runs. It should become a full Data Health dashboard: per-signal freshness, gap detection, actionable remediation steps, and a "last known good" state per source.

### What to build

**New Admin views:**

1. **Signal health grid** — per metric (RHR, HRV, sleep, weight, activities), shows:
   - Last received date
   - Gap count (days missing in last 30)
   - Status badge: Fresh / Stale / Missing
2. **Sync diagnostic panel** — for each `SyncSourceRun`:
   - HTTP status, error code, error message
   - "Fix it" link/hint for common errors (401 → re-auth, timeout → retry, 429 → rate limit)
3. **Data gaps timeline** — calendar heatmap of days with missing wellness data
4. **Manual data entry** — ability to manually add a `DailyMetrics` row for a past date (for travel days, etc.)

**Logic changes:**
- Add `getDataHealthReport(userId)` to `web/lib/sync/status.ts`
- Report includes: per-source last success, gap count, stale threshold breach
- Expose as JSON API: `GET /api/admin/data-health`

### Acceptance Criteria

- [ ] Signal health grid renders with correct Fresh/Stale/Missing badges
- [ ] Gap count is accurate for the last 30 days
- [ ] Sync error messages are human-readable (not raw HTTP codes)
- [ ] Manual `DailyMetrics` entry form works and persists correctly
- [ ] `getDataHealthReport()` is unit-tested
- [ ] Data Health report is used by the confidence model (Issue 3)

### Dependencies

- Issue 3 (confidence model is the consumer of health report data)
