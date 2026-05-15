import { cookies } from "next/headers";
import { redirect } from "next/navigation";

async function login(formData: FormData) {
  "use server";
  const pin = String(formData.get("pin") ?? "");
  const expected = process.env.DASHBOARD_PIN;

  if (!expected || pin !== expected) {
    redirect("/login?error=1");
  }

  const jar = await cookies();
  jar.set("dashboard_pin", pin, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  redirect("/");
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;

  return (
    <main className="mx-auto max-w-sm p-8 space-y-4">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <form action={login} className="space-y-3">
        <input
          name="pin"
          type="password"
          inputMode="numeric"
          autoComplete="off"
          autoFocus
          placeholder="PIN"
          className="w-full rounded border border-gray-300 px-3 py-2 text-base"
        />
        <button
          type="submit"
          className="w-full rounded bg-black px-3 py-2 text-white"
        >
          Continue
        </button>
        {error ? (
          <p className="text-sm text-red-600">Incorrect PIN.</p>
        ) : null}
      </form>
    </main>
  );
}
