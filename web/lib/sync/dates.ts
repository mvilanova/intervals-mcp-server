// Strict YYYY-MM-DD → UTC Date. `new Date("2024-02-30")` silently
// normalizes to 2024-03-01 in some engines and returns NaN in others;
// neither is what we want. This helper rejects both: the string must
// match the format exactly AND survive a year/month/day round-trip
// without normalization.
//
// Shared by `intervals.ts` (validating per-row dates from the Intervals
// payload) and `sourceRun.ts` (validating the requestedFrom/requestedTo
// window before it gets persisted).
export function parseUtcDateOnly(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return parsed;
}
