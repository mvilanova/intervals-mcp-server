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
