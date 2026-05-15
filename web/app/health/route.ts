import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    await prisma.$queryRaw`SELECT 1`;
    return NextResponse.json({
      ok: true,
      db: "up",
      latestSync: null,
    });
  } catch {
    return NextResponse.json(
      { ok: false, db: "down", latestSync: null },
      { status: 503 },
    );
  }
}
