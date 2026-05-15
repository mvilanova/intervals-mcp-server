-- AlterTable
ALTER TABLE "DailyMetrics" ADD COLUMN     "carbsGrams" DOUBLE PRECISION,
ADD COLUMN     "fatGrams" DOUBLE PRECISION,
ADD COLUMN     "kcalConsumed" INTEGER,
ADD COLUMN     "proteinGrams" DOUBLE PRECISION;

-- CreateTable
CREATE TABLE "SyncRun" (
    "id" TEXT NOT NULL,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" TIMESTAMP(3),
    "mode" TEXT NOT NULL,
    "wellnessUpserts" INTEGER NOT NULL DEFAULT 0,
    "activityUpserts" INTEGER NOT NULL DEFAULT 0,
    "weightUpserts" INTEGER NOT NULL DEFAULT 0,
    "errors" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

    CONSTRAINT "SyncRun_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "SyncRun_startedAt_idx" ON "SyncRun"("startedAt");

-- Partial unique index: at most one in-progress SyncRun at a time.
-- Prisma's schema doesn't model partial unique indexes, so this index is
-- the authoritative concurrency guard. Application code catches P2002 from
-- syncRun.create() and surfaces it as "already in progress".
CREATE UNIQUE INDEX "SyncRun_single_pending_idx"
    ON "SyncRun" ((1))
    WHERE "finishedAt" IS NULL;
