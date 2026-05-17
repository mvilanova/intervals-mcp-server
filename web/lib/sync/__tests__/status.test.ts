import { describe, expect, it } from "vitest";
import { deriveStatus } from "../status";

describe("deriveStatus", () => {
  it("returns `error` when an errorMessage is present, regardless of counts", () => {
    expect(
      deriveStatus({
        errorMessage: "Intervals.icu 401 Unauthorized",
        fetchedCount: 0,
        upsertedCount: 0,
        skippedCount: 0,
      }),
    ).toBe("error");

    // Even if some writes landed before the error.
    expect(
      deriveStatus({
        errorMessage: "parse_error: unexpected schema",
        fetchedCount: 10,
        upsertedCount: 4,
        skippedCount: 0,
      }),
    ).toBe("error");
  });

  it("returns `no_data` when fetch succeeded but remote returned zero rows", () => {
    expect(
      deriveStatus({
        errorMessage: null,
        fetchedCount: 0,
        upsertedCount: 0,
        skippedCount: 0,
      }),
    ).toBe("no_data");
  });

  it("returns `up_to_date` when rows were fetched but nothing was written", () => {
    expect(
      deriveStatus({
        errorMessage: null,
        fetchedCount: 12,
        upsertedCount: 0,
        skippedCount: 0,
      }),
    ).toBe("up_to_date");
  });

  it("returns `ok` when rows were written cleanly with no skips", () => {
    expect(
      deriveStatus({
        errorMessage: null,
        fetchedCount: 31,
        upsertedCount: 31,
        skippedCount: 0,
      }),
    ).toBe("ok");
  });

  it("returns `partial` when some rows were written and some were skipped", () => {
    expect(
      deriveStatus({
        errorMessage: null,
        fetchedCount: 10,
        upsertedCount: 7,
        skippedCount: 3,
      }),
    ).toBe("partial");
  });

  it("returns `partial` when rows were skipped even if none were written", () => {
    expect(
      deriveStatus({
        errorMessage: null,
        fetchedCount: 10,
        upsertedCount: 0,
        skippedCount: 3,
      }),
    ).toBe("partial");
  });

  it("treats undefined errorMessage the same as null", () => {
    expect(
      deriveStatus({
        fetchedCount: 5,
        upsertedCount: 5,
        skippedCount: 0,
      }),
    ).toBe("ok");
  });
});
