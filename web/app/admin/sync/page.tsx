import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/db";
import { COOKIE_NAME, verifySession } from "@/lib/auth";
import { syncIntervals } from "@/lib/sync/intervals";
import { Button } from "@/app/_components/ui/button";

export const dynamic = "force-dynamic";

const SOURCES = ["wellness", "activities", "weight"] as const;
type Source = (typeof SOURCES)[number];

const SOURCE_LABEL: Record<Source, string> = {
  wellness: "Wellness",
  activities: "Training activities",
  weight: "Weight",
};

// Maps the raw DB status string to user-facing wording. Anything we
// don't recognize falls through to the raw value rather than silently
// hiding — that way an unexpected status surfaces in the UI instead of
// being masked.
const STATUS_LABEL: Record<string, string> = {
  ok: "OK",
  up_to_date: "Up to date",
  no_data: "No data returned",
  partial: "Partial",
  error: "Pull failed",
};

const STATUS_CLASS: Record<string, string> = {
  ok: "bg-green-100 text-green-800",
  up_to_date: "bg-blue-100 text-blue-800",
  no_data: "bg-gray-100 text-gray-700",
  partial: "bg-yellow-100 text-yellow-900",
  error: "bg-red-100 text-red-800",
};

/**
 * Ensures an authenticated session is present and redirects to the login page if not.
 *
 * If no valid session is found the function redirects the request to `/login`.
 */
async function requireSession() {
  const jar = await cookies();
  if (!verifySession(jar.get(COOKIE_NAME)?.value)) {
    redirect("/login");
  }
}

/**
 * Starts a synchronization run based on form input and refreshes the admin sync page.
 *
 * Enforces an authenticated session. If the sync operation fails, throws an Error containing the underlying failure message.
 *
 * @param formData - Form data with an optional `"mode"` field; `"full"` triggers a full sync, any other value triggers the recent sync mode.
 */
async function runSync(formData: FormData) {
  "use server";
  await requireSession();

  // Concurrency is enforced atomically at the DB layer via the partial
  // unique index on SyncRun WHERE finishedAt IS NULL. syncIntervals()
  // throws "A sync is already in progress" if another run owns the lock.
  const mode = formData.get("mode") === "full" ? "full" : "recent";
  try {
    await syncIntervals({ mode });
  } catch (err) {
    console.error("[admin] sync failed:", err);
    throw new Error(
      `Sync failed: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  revalidatePath("/admin/sync");
}

/**
 * Format two dates as a YYYY-MM-DD range separated by `→`.
 *
 * @param from - Start date of the range
 * @param to - End date of the range
 * @returns The date range string in `YYYY-MM-DD → YYYY-MM-DD` format
 */
function formatDateRange(from: Date, to: Date): string {
  return `${from.toISOString().slice(0, 10)} → ${to.toISOString().slice(0, 10)}`;
}

/**
 * Formats a Date as `YYYY-MM-DD HH:mm UTC`, or returns an em dash when no date is provided.
 *
 * @param d - The date to format, or `null` to indicate absence
 * @returns The formatted timestamp `YYYY-MM-DD HH:mm UTC`, or `"—"` when `d` is `null`
 */
function formatTime(d: Date | null): string {
  if (!d) return "—";
  return d.toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

/**
 * Render the admin "Sync" page showing per-source sync status and recent sync runs.
 *
 * Renders controls to trigger a recent or full sync, a card for each source showing the latest run's metrics and any error details plus the last successful run, and a list of recent sync runs.
 *
 * @returns The page's root JSX element containing sync controls, per-source status cards, and recent runs.
 */
export default async function AdminSyncPage() {
  await requireSession();

  const [runs, latestPerSource] = await Promise.all([
    prisma.syncRun.findMany({
      orderBy: { startedAt: "desc" },
      take: 10,
      include: { sources: true },
    }),
    // For each source, the most recent run we have (used for the cards).
    // Two queries (latest overall, latest successful) keep this simple and
    // index-friendly via the SyncSourceRun_source_startedAt_idx.
    Promise.all(
      SOURCES.map(async (source) => {
        const [latest, lastSuccess] = await Promise.all([
          prisma.syncSourceRun.findFirst({
            where: { source },
            orderBy: { startedAt: "desc" },
          }),
          prisma.syncSourceRun.findFirst({
            where: { source, status: { in: ["ok", "up_to_date", "no_data"] } },
            orderBy: { startedAt: "desc" },
          }),
        ]);
        return { source, latest, lastSuccess };
      }),
    ),
  ]);

  return (
    <main className="mx-auto max-w-3xl p-8 space-y-8">
      <h1 className="text-2xl font-semibold">Sync</h1>

      <section className="flex gap-2">
        <form action={runSync}>
          <input type="hidden" name="mode" value="recent" />
          <Button type="submit">Sync now (last 3d)</Button>
        </form>
        <form action={runSync}>
          <input type="hidden" name="mode" value="full" />
          <Button type="submit" variant="outline">
            Full sync (30d)
          </Button>
        </form>
      </section>

      <section>
        <h2 className="text-lg font-medium mb-3">Per-source status</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {latestPerSource.map(({ source, latest, lastSuccess }) => {
            // Distinguish "never run" (latest is null) from any real status —
            // showing a result badge for a source that's never produced a row
            // would mislead admins on a fresh deploy.
            const status = latest?.status;
            const statusLabel = status ? (STATUS_LABEL[status] ?? status) : null;
            const statusClass = status
              ? (STATUS_CLASS[status] ?? "bg-gray-100 text-gray-700")
              : null;
            return (
              <div
                key={source}
                className="rounded border border-gray-200 p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">{SOURCE_LABEL[source]}</h3>
                  {status && (
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${statusClass}`}
                    >
                      {statusLabel}
                    </span>
                  )}
                </div>
                {latest ? (
                  <dl className="text-xs space-y-1 text-gray-700">
                    <div>
                      <dt className="inline text-gray-500">Window: </dt>
                      <dd className="inline">
                        {formatDateRange(latest.requestedFrom, latest.requestedTo)}
                      </dd>
                    </div>
                    <div>
                      <dt className="inline text-gray-500">Fetched: </dt>
                      <dd className="inline">{latest.fetchedCount ?? "—"}</dd>
                      <span className="mx-1 text-gray-400">·</span>
                      <dt className="inline text-gray-500">Written: </dt>
                      <dd className="inline">{latest.upsertedCount}</dd>
                      <span className="mx-1 text-gray-400">·</span>
                      <dt className="inline text-gray-500">Unchanged: </dt>
                      <dd className="inline">{latest.unchangedCount}</dd>
                      {latest.skippedCount > 0 && (
                        <>
                          <span className="mx-1 text-gray-400">·</span>
                          <dt className="inline text-gray-500">Skipped: </dt>
                          <dd className="inline">{latest.skippedCount}</dd>
                        </>
                      )}
                    </div>
                    {status === "error" && (
                      <div className="pt-1 border-t border-gray-100">
                        {latest.httpStatus != null && (
                          <div>
                            <dt className="inline text-gray-500">HTTP: </dt>
                            <dd className="inline">{latest.httpStatus}</dd>
                          </div>
                        )}
                        {latest.errorMessage && (
                          <div className="text-red-700 break-words">
                            {latest.errorMessage}
                          </div>
                        )}
                      </div>
                    )}
                    <div className="pt-1 text-gray-500">
                      Last success: {formatTime(lastSuccess?.startedAt ?? null)}
                    </div>
                  </dl>
                ) : (
                  <p className="text-xs text-gray-500">No syncs recorded yet.</p>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-medium mb-2">Recent runs</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-gray-500">No syncs yet.</p>
        ) : (
          <ul className="text-sm space-y-1">
            {runs.map((r) => (
              <li
                key={r.id}
                className="font-mono whitespace-pre-wrap break-all"
              >
                {r.startedAt.toISOString()} {r.mode}{" "}
                {r.finishedAt ? "ok" : "in-progress"}{" "}
                w:{r.wellnessUpserts} a:{r.activityUpserts} wt:{r.weightUpserts}
                {r.errors.length > 0 ? ` errors=${r.errors.join("; ")}` : ""}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
