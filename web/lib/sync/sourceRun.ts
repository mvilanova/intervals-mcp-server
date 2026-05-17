import { prisma } from "@/lib/db";
import { parseUtcDateOnly } from "./dates";
import { deriveStatus, SyncSourceName, SyncSourceStatus } from "./status";

// What a source's run function reports back. All counts are nullable
// only when they're genuinely unknowable (e.g. parsing failed before
// we could count fetched rows). Callers that can produce a number
// should — `null` flows through to the UI as "unknown", which is
// uglier than a real count.
export type SourceRunOutcome = {
  fetchedCount: number | null;
  parsedCount: number | null;
  upsertedCount: number;
  skippedCount?: number;
  httpStatus?: number;
};

export type SourceRunResult = {
  source: SyncSourceName;
  status: SyncSourceStatus;
  upsertedCount: number;
  errorMessage: string | null;
};

export type PartialOutcomeOnError = SourceRunOutcome;

export class SourceRunError extends Error {
  public readonly partial?: PartialOutcomeOnError;
  public readonly status?: number;
  public readonly code?: string;

  constructor(
    message: string,
    opts: {
      partial?: PartialOutcomeOnError;
      status?: number;
      code?: string;
      cause?: unknown;
    } = {},
  ) {
    super(message, { cause: opts.cause });
    this.name = "SourceRunError";
    this.partial = opts.partial;
    this.status = opts.status;
    this.code = opts.code;
  }
}


type IntervalsErrorShape = {
  status?: number;
  code?: string;
  message: string;
};

/**
 * Type guard that determines whether a value matches the `IntervalsErrorShape`.
 *
 * Checks that the value is an `Error` with a string `message` and that it contains
 * either a `status` or `code` property.
 *
 * @param err - The value to test
 * @returns `true` if `err` is an `IntervalsErrorShape`, `false` otherwise.
 */
function isIntervalsErrorShape(err: unknown): err is IntervalsErrorShape {
  return (
    err instanceof Error &&
    ("status" in err || "code" in err) &&
    typeof err.message === "string"
  );
}

// Eager-create the source row so a crash mid-run leaves evidence that
// the source was attempted but never finished. The placeholder status
// is `error` — the most pessimistic reading, which gets overwritten on
// successful completion. This row is intentionally NOT inside a
// transaction with the upserts: source rows are for observability, so
/**
 * Runs a single source sync, records an observability row in the database, and returns a summary of the run.
 *
 * Creates an initial `syncSourceRun` row (status `"error"`) before invoking `args.run()`, then updates that row with counts, HTTP status, final status, and `finishedAt` on success or with error metadata on failure.
 *
 * @param args.syncRunId - The enclosing sync run's ID
 * @param args.source - The name of the sync source being run
 * @param args.requestedFrom - Inclusive start date for the run in `YYYY-MM-DD` format
 * @param args.requestedTo - Inclusive end date for the run in `YYYY-MM-DD` format
 * @param args.run - Async callback that performs the source sync and returns a `SourceRunOutcome`
 * @returns The `SourceRunResult` summarizing the source, final status, number of upserted records, and an `errorMessage` when the run failed
 */
export async function runSourceSync(args: {
  syncRunId: string;
  source: SyncSourceName;
  requestedFrom: string; // YYYY-MM-DD
  requestedTo: string;
  run: () => Promise<SourceRunOutcome>;
}): Promise<SourceRunResult> {
  // Reject malformed window dates before persisting — current callers
  // always pass valid YYYY-MM-DD via dateWindow(), but the signature
  // accepts any string and `new Date()` would silently coerce garbage
  // into wrong dates or NaN, both of which would land in the DB.
  const fromDate = parseUtcDateOnly(args.requestedFrom);
  const toDate = parseUtcDateOnly(args.requestedTo);
  if (!fromDate || !toDate) {
    throw new Error(
      `runSourceSync: requestedFrom/requestedTo must be valid YYYY-MM-DD dates (got from="${args.requestedFrom}", to="${args.requestedTo}")`,
    );
  }

  const row = await prisma.syncSourceRun.create({
    data: {
      syncRunId: args.syncRunId,
      source: args.source,
      status: "error",
      requestedFrom: fromDate,
      requestedTo: toDate,
    },
  });

  try {
    const outcome = await args.run();
    const skipped = outcome.skippedCount ?? 0;
    const unchanged =
      outcome.parsedCount != null
        ? Math.max(outcome.parsedCount - outcome.upsertedCount - skipped, 0)
        : 0;
    const status = deriveStatus({
      errorMessage: null,
      fetchedCount: outcome.fetchedCount,
      upsertedCount: outcome.upsertedCount,
      skippedCount: skipped,
    });

    await prisma.syncSourceRun.update({
      where: { id: row.id },
      data: {
        status,
        fetchedCount: outcome.fetchedCount,
        parsedCount: outcome.parsedCount,
        upsertedCount: outcome.upsertedCount,
        unchangedCount: unchanged,
        skippedCount: skipped,
        httpStatus: outcome.httpStatus,
        finishedAt: new Date(),
      },
    });

    return {
      source: args.source,
      status,
      upsertedCount: outcome.upsertedCount,
      errorMessage: null,
    };
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : String(err);
    const partial = err instanceof SourceRunError ? err.partial : undefined;
    const skipped = partial?.skippedCount ?? 0;
    const unchanged =
      partial?.parsedCount != null
        ? Math.max(partial.parsedCount - partial.upsertedCount - skipped, 0)
        : 0;
    const httpStatus =
      partial?.httpStatus ?? (isIntervalsErrorShape(err) ? err.status : undefined);
    const errorCode = isIntervalsErrorShape(err) ? err.code : undefined;

    await prisma.syncSourceRun.update({
      where: { id: row.id },
      data: {
        status: "error",
        fetchedCount: partial?.fetchedCount,
        parsedCount: partial?.parsedCount,
        upsertedCount: partial?.upsertedCount ?? 0,
        unchangedCount: unchanged,
        skippedCount: skipped,
        httpStatus,
        errorCode,
        errorMessage,
        finishedAt: new Date(),
      },
    });

    return {
      source: args.source,
      status: "error",
      upsertedCount: partial?.upsertedCount ?? 0,
      errorMessage,
    };
  }
}
