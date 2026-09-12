/**
 * The small vocabulary the public pages are built from, in the same look as
 * the arbiter's desk: hairlines, flat surfaces, one accent.
 */

import type { ReactNode } from "react";
import { Link } from "react-router";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function Card({
  children,
  className,
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
}) {
  return <Tag className={cx("rounded-lg border border-line bg-card", className)}>{children}</Tag>;
}

export function Chip({
  tone,
  children,
  className,
  title,
}: {
  tone: "neutral" | "amber" | "emerald" | "blue";
  children: ReactNode;
  className?: string;
  title?: string;
}) {
  const style = {
    neutral: "border-line bg-subtle text-ink-2",
    amber: "border-amber-line bg-amber-soft text-amber-text",
    emerald: "border-emerald-line bg-emerald-soft text-emerald-text",
    blue: "border-blue-line bg-blue-soft text-blue-text",
  }[tone];
  return (
    <span
      title={title}
      className={cx(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-label-sm whitespace-nowrap [&>svg]:size-3",
        style,
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Banner({
  tone,
  children,
  className,
}: {
  tone: "error" | "warn" | "info";
  children: ReactNode;
  className?: string;
}) {
  const style = {
    error: "border-rose-line bg-rose-soft text-rose-text",
    warn: "border-amber-line bg-amber-soft text-amber-text",
    info: "border-blue-line bg-blue-soft text-blue-text",
  }[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cx("rounded-md border px-3 py-2 text-body-sm", style, className)}>
      {children}
    </div>
  );
}

export function Skeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div role="status" className={cx("flex flex-col gap-2 p-4", className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-5 animate-pulse rounded bg-subtle" />
      ))}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg border border-dashed border-line-strong px-4 py-10 text-center">
      <p className="text-headline-sm">{title}</p>
      {children && <p className="max-w-md text-body-sm text-ink-2">{children}</p>}
    </div>
  );
}

/**
 * A row of tabs that are links, so the choice sits in the URL and survives a
 * reload. The caller says which is active: the tabs differ only in their
 * query string, which the router's own active matching does not look at.
 */
export function Tabs({
  items,
  ariaLabel,
}: {
  items: { to: string; label: ReactNode; active: boolean }[];
  ariaLabel: string;
}) {
  return (
    <nav aria-label={ariaLabel} className="flex gap-1 overflow-x-auto">
      {items.map((item) => (
        <Link
          key={item.to}
          to={item.to}
          aria-current={item.active ? "page" : undefined}
          className={cx(
            "inline-flex min-h-9 items-center rounded-md border px-3 text-sm whitespace-nowrap transition-colors",
            item.active
              ? "border-blue-line bg-blue-soft font-semibold text-blue-text"
              : "border-transparent font-medium text-ink-2 hover:bg-subtle hover:text-ink",
          )}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex w-fit items-center gap-1 text-body-sm font-medium text-ink-2 hover:text-ink"
    >
      ← {children}
    </Link>
  );
}
