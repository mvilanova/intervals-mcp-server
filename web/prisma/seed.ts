import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const email = process.env.SEED_USER_EMAIL ?? "you@example.com";
  const targetWeight = process.env.SEED_TARGET_WEIGHT
    ? Number(process.env.SEED_TARGET_WEIGHT)
    : null;
  const targetDate = process.env.SEED_TARGET_DATE
    ? new Date(process.env.SEED_TARGET_DATE)
    : null;

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
