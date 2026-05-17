-- CreateTable
CREATE TABLE "SyncSourceRun" (
    "id" TEXT NOT NULL,
    "syncRunId" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "requestedFrom" DATE NOT NULL,
    "requestedTo" DATE NOT NULL,
    "fetchedCount" INTEGER,
    "parsedCount" INTEGER,
    "upsertedCount" INTEGER NOT NULL DEFAULT 0,
    "unchangedCount" INTEGER NOT NULL DEFAULT 0,
    "skippedCount" INTEGER NOT NULL DEFAULT 0,
    "httpStatus" INTEGER,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" TIMESTAMP(3),

    CONSTRAINT "SyncSourceRun_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "SyncSourceRun_syncRunId_source_key" ON "SyncSourceRun"("syncRunId", "source");

-- CreateIndex
CREATE INDEX "SyncSourceRun_syncRunId_idx" ON "SyncSourceRun"("syncRunId");

-- CreateIndex
CREATE INDEX "SyncSourceRun_source_startedAt_idx" ON "SyncSourceRun"("source", "startedAt");

-- AddForeignKey
ALTER TABLE "SyncSourceRun" ADD CONSTRAINT "SyncSourceRun_syncRunId_fkey" FOREIGN KEY ("syncRunId") REFERENCES "SyncRun"("id") ON DELETE CASCADE ON UPDATE CASCADE;
