import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SyncStatusPill } from "../SyncStatusPill";

// Mock next/link to render a plain anchor
vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

import React from "react";

describe("SyncStatusPill", () => {
  describe("fresh (not stale)", () => {
    it("renders relative text", () => {
      render(
        <SyncStatusPill status={{ stale: false, relative: "synced 2m ago" }} />,
      );
      expect(screen.getByText("synced 2m ago")).toBeInTheDocument();
    });

    it("links to /admin/sync", () => {
      render(
        <SyncStatusPill status={{ stale: false, relative: "synced 2m ago" }} />,
      );
      expect(screen.getByRole("link")).toHaveAttribute("href", "/admin/sync");
    });

    it("applies emerald color classes when not stale", () => {
      render(
        <SyncStatusPill status={{ stale: false, relative: "synced 2m ago" }} />,
      );
      const link = screen.getByRole("link");
      expect(link.className).toContain("bg-emerald-50");
      expect(link.className).toContain("text-emerald-900");
    });

    it("does not apply amber classes when not stale", () => {
      render(
        <SyncStatusPill status={{ stale: false, relative: "synced 2m ago" }} />,
      );
      const link = screen.getByRole("link");
      expect(link.className).not.toContain("bg-amber-50");
    });
  });

  describe("stale", () => {
    it("renders relative text for stale status", () => {
      render(
        <SyncStatusPill status={{ stale: true, relative: "never synced" }} />,
      );
      expect(screen.getByText("never synced")).toBeInTheDocument();
    });

    it("applies amber color classes when stale", () => {
      render(
        <SyncStatusPill status={{ stale: true, relative: "never synced" }} />,
      );
      const link = screen.getByRole("link");
      expect(link.className).toContain("bg-amber-50");
      expect(link.className).toContain("text-amber-900");
    });

    it("does not apply emerald classes when stale", () => {
      render(
        <SyncStatusPill status={{ stale: true, relative: "never synced" }} />,
      );
      const link = screen.getByRole("link");
      expect(link.className).not.toContain("bg-emerald-50");
    });

    it("renders stale indicator dot with amber class", () => {
      render(
        <SyncStatusPill status={{ stale: true, relative: "synced 8h ago" }} />,
      );
      // The indicator span has aria-hidden and bg-amber-500 class
      const dot = screen.getByRole("link").querySelector("[aria-hidden]");
      expect(dot).not.toBeNull();
      expect(dot!.className).toContain("bg-amber-500");
    });

    it("renders fresh indicator dot with emerald class", () => {
      render(
        <SyncStatusPill status={{ stale: false, relative: "synced 1h ago" }} />,
      );
      const dot = screen.getByRole("link").querySelector("[aria-hidden]");
      expect(dot).not.toBeNull();
      expect(dot!.className).toContain("bg-emerald-500");
    });
  });
});