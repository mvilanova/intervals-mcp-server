import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const mockPrisma = {
    syncSourceRun: {
      create: vi.fn(),
      update: vi.fn(),
    },
  };
  return { mockPrisma };
});

vi.mock("@/lib/db", () => ({ prisma: mocks.mockPrisma }));

import { runSourceSync, SourceRunError } from "../sourceRun";

describe("runSourceSync", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.mockPrisma.syncSourceRun.create.mockResolvedValue({ id: "source-run-1" });
    mocks.mockPrisma.syncSourceRun.update.mockResolvedValue({});
  });

  it("persists partial counts when a source fails after writing rows", async () => {
    const result = await runSourceSync({
      syncRunId: "sync-run-1",
      source: "wellness",
      requestedFrom: "2026-05-01",
      requestedTo: "2026-05-17",
      run: async () => {
        throw new SourceRunError("database write failed", {
          partial: {
            fetchedCount: 5,
            parsedCount: 5,
            upsertedCount: 2,
            skippedCount: 1,
            httpStatus: 200,
          },
        });
      },
    });

    expect(mocks.mockPrisma.syncSourceRun.update).toHaveBeenCalledWith({
      where: { id: "source-run-1" },
      data: expect.objectContaining({
        status: "error",
        fetchedCount: 5,
        parsedCount: 5,
        upsertedCount: 2,
        skippedCount: 1,
        unchangedCount: 2,
        httpStatus: 200,
        errorMessage: "database write failed",
      }),
    });
    expect(result).toEqual({
      source: "wellness",
      status: "error",
      upsertedCount: 2,
      errorMessage: "database write failed",
    });
  });
  it("rejects invalid requested windows before persisting", async () => {
    await expect(
      runSourceSync({
        syncRunId: "sync-run-1",
        source: "wellness",
        requestedFrom: "2026-02-30",
        requestedTo: "2026-05-17",
        run: async () => ({
          fetchedCount: 0,
          parsedCount: 0,
          upsertedCount: 0,
        }),
      }),
    ).rejects.toThrow("requestedFrom/requestedTo must be valid YYYY-MM-DD dates");

    expect(mocks.mockPrisma.syncSourceRun.create).not.toHaveBeenCalled();
  });

});
