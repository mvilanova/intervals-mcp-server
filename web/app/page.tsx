import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function Home() {
  const user = await prisma.user.findFirst();

  return (
    <main className="mx-auto max-w-2xl p-8 space-y-4">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      {user ? (
        <div className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
          <p>Hello, {user.email}.</p>
          {user.targetWeight ? (
            <p>Target weight: {user.targetWeight} kg</p>
          ) : null}
          {user.targetDate ? (
            <p>Target date: {user.targetDate.toISOString().slice(0, 10)}</p>
          ) : null}
        </div>
      ) : (
        <p className="text-sm text-gray-500">
          No user seeded yet. Run <code>npm run db:seed</code> in <code>web/</code>.
        </p>
      )}
    </main>
  );
}
