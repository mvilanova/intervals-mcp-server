# getmAIlean Product Direction

## North Star

getmAIlean is not a fitness dashboard with AI sprinkles.

It is an AI-aided fitness operating system that turns training, recovery, nutrition, weight, and context into one clear daily decision.

The core promise:

> Tell me what to do today, why, and what to watch for.

## Product Principles

1. Coach before dashboard.
2. Decisions before charts.
3. Explain meaning, not just metrics.
4. Rules first, LLM later.
5. Confidence matters when data is missing.
6. The UI serves the coaching loop.
7. Every feature should improve daily adherence, recovery, or decision quality.

## Core User Loop

1. Sense: collect training, recovery, nutrition, weight, meal adherence, sync health, and relevant context.
2. Interpret: identify readiness, risk, adherence, trend direction, and data confidence.
3. Decide: recommend today's action.
4. Coach: explain why, what to do, what to avoid, and what to watch for.
5. Learn: collect feedback and adjust future recommendations.

## Main Surfaces

### Today

One recommendation, why, action checklist, risk flags, meal compliance, and data confidence.

### Trends

Weight, recovery, load, and adherence signals explained in plain language. The app should tell the user what matters, not just graph everything.

### Plan

Weekly target, training/recovery structure, and nutrition focus.

### Coach Memory

What the app knows about the user: goals, injuries, preferences, constraints, and repeated failure modes.

### Admin/Data Health

Sync status, missing data, stale integrations, and confidence warnings.

## Feature Gate

Before building any feature, ask:

- Does this help the user decide what to do today?
- Does this improve the coach's judgment?
- Does this improve adherence, recovery, or body-composition progress?
- Is it just prettier, or does it make the app smarter?

If it is only polish, it comes after the coaching loop.

## Execution Model

- This document is the product north star and direction SSOT.
- Fitness intelligence specs explain the decision engine beneath the product direction.
- GitHub issues are execution chunks derived from the product direction and specs.
- PRs should state how they move the product toward the coaching loop.
- If a GitHub issue conflicts with this direction, pause and ask the maintainer before implementing.
