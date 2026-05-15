import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const email = process.env.SEED_USER_EMAIL ?? "you@example.com";

  let targetWeight: number | null = null;
  if (process.env.SEED_TARGET_WEIGHT) {
    const parsed = Number(process.env.SEED_TARGET_WEIGHT);
    if (!Number.isFinite(parsed)) {
      throw new Error(
        `Invalid SEED_TARGET_WEIGHT: "${process.env.SEED_TARGET_WEIGHT}"`,
      );
    }
    targetWeight = parsed;
  }

  let targetDate: Date | null = null;
  if (process.env.SEED_TARGET_DATE) {
    const parsed = new Date(process.env.SEED_TARGET_DATE);
    if (Number.isNaN(parsed.getTime())) {
      throw new Error(
        `Invalid SEED_TARGET_DATE: "${process.env.SEED_TARGET_DATE}"`,
      );
    }
    targetDate = parsed;
  }

  // Only include fields the env actually set so re-running the seed never
  // clobbers values set via the dashboard UI.
  const updateData = {
    ...(targetWeight !== null && { targetWeight }),
    ...(targetDate !== null && { targetDate }),
  };

  const user = await prisma.user.upsert({
    where: { email },
    update: updateData,
    create: {
      email,
      targetWeight: targetWeight ?? 65,
      targetDate,
    },
  });

  console.log(`Seeded user ${user.email} (id=${user.id})`);
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
