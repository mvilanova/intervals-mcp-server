import Link from "next/link";
import type { SyncStatus } from "@/lib/queries/today";

type Props = {
  status: SyncStatus;
};

export function SyncStatusPill({ status }: Props) {
  return (
    <Link
      href="/admin/sync"
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs ${
        status.stale
          ? "bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200"
          : "bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"
      }`}
    >
      <span
        aria-hidden
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          status.stale ? "bg-amber-500" : "bg-emerald-500"
        }`}
      />
      {status.relative}
    </Link>
  );
}
