# Changelog

## Unreleased

### Fixed

- `get_event_by_id` called `/athlete/{id}/event/{eventId}` and always got 404; it now uses `/events/{eventId}`.
- `get_events` showed every event as `Type: Other`. Events now show category, sport, planned load and planned time (`N/A` when Intervals.icu has none); races are detected from `RACE_A/B/C`. `get_event_by_id` shows the same fields.
- `get_activity_details` looks up the gear name with the athlete who owns the activity (a coached athlete), not always with `ATHLETE_ID`.
- `add_or_update_event` and `add_or_update_note` no longer send empty fields on update. Renaming an event keeps its description, date, type and category, and an update no longer turns a note into a workout or moves the event to today.

### Added

- `get_coach_report`: optional `athlete_id` for coached athletes (default: `ATHLETE_ID`).
- `add_or_update_event`: `workout_type` is optional (needed only when creating, inferred from the name otherwise) and a new optional `category` (e.g. `RACE_A`).
- `get_coach_report` schema 1.1 with a projection mode for a future `end_date`: `period.mode`, `load.actual` / `load.projected`, `recovery.as_of`, a `plan` section (planned load per week and sport, rest days, projected CTL/ramp/TSB, races) and the flags `ramp_planned_high`, `tsb_planned_low` and `planned_rest_days_low`. Flags carry `basis: actual|projection` in projection mode.

### Changed

- All tools check a passed `athlete_id` (digits or `i` + digits) before calling the API; an empty `athlete_id` falls back to `ATHLETE_ID` instead of returning an error.
- `get_coach_report`: `load.src` is `api_incl_planned` for values that include planned workouts; `recomputed_without_planned` is only used when a value up to today was really recomputed without planned load. Without a future end date the report content is unchanged (only `schema_version` and `period.mode` are new).
