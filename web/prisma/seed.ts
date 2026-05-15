import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  const email = process.env.SEED_USER_EMAIL ?? "you@example.com";
  const targetWeight = process.env.SEED_TARGET_WEIGHT
    ? Number(process.env.SEED_TARGET_WEIGHT)
    : 65;
  const targetDate = process.env.SEED_TARGET_DATE
    ? new Date(process.env.SEED_TARGET_DATE)
    : null;

  const user = await prisma.user.upsert({
    where: { email },
    update: {
      targetWeight,
      targetDate: targetDate ?? undefined,
    },
    create: {
      email,
      targetWeight,
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
