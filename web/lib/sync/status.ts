export type SyncSourceName = "wellness" | "activities" | "weight";

export type SyncSourceStatus =
  | "ok"
  | "up_to_date"
  | "no_data"
  | "partial"
  | "error";

export type DeriveStatusInput = {
  errorMessage?: string | null;
  fetchedCount: number | null;
  upsertedCount: number;
  skippedCount: number;
};

// Pure status derivation. Order matters:
//   1. An errorMessage always wins — a partial write that hit an error
//      is still an error from the user's perspective.
//   2. Fetched-but-nothing is `no_data` (the ambiguous-zero case the
//      whole feature exists to disambiguate).
//   3. Any skipped rows make the run `partial`, even when nothing landed —
//      "we couldn't process some of what we fetched" is a partial outcome
//      regardless of whether anything else was written.
//   4. Wrote-cleanly is `ok`.
//   5. Fetched-but-no-writes-or-skips is `up_to_date` (already-synced rows).
// `fetchedCount === null` happens when parsing failed before we could
// even count rows; that path always carries an errorMessage, so rule 1
// catches it.
export function deriveStatus(input: DeriveStatusInput): SyncSourceStatus {
  if (input.errorMessage) return "error";
  if (input.fetchedCount === 0) return "no_data";
  if (input.skippedCount > 0) return "partial";
  if (input.upsertedCount > 0) return "ok";
  return "up_to_date";
}
