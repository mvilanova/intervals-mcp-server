import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { prisma } from "@/lib/db";
import { COOKIE_NAME, verifySession } from "@/lib/auth";
import { syncIntervals } from "@/lib/sync/intervals";
import { Button } from "@/app/_components/ui/button";

export const dynamic = "force-dynamic";

async function requireSession() {
  const jar = await cookies();
  if (!verifySession(jar.get(COOKIE_NAME)?.value)) {
    redirect("/login");
  }
}

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

export default async function AdminSyncPage() {
  await requireSession();
  const runs = await prisma.syncRun.findMany({
    orderBy: { startedAt: "desc" },
    take: 10,
  });

  return (
    <main className="mx-auto max-w-2xl p-8 space-y-6">
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
