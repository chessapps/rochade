/**
 * The top of a screen that is not the tournament home: the way back, the
 * name of the place, and what it is for in one line.
 */

import type { ReactNode } from "react";
import { Link } from "react-router";

import { ArrowLeft } from "./icons";
import { cx } from "./ui";

export function PageHeader({
  back,
  title,
  lead,
  actions,
  className,
}: {
  back?: { to: string; label: string };
  title: ReactNode;
  lead?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cx("flex flex-col gap-1", className)}>
      {back && (
        <Link
          to={back.to}
          className="inline-flex w-fit items-center gap-1 text-body-sm font-medium text-ink-2 hover:text-ink [&>svg]:size-3.5"
        >
          <ArrowLeft />
          {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-headline-md">{title}</h1>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {lead && <p className="max-w-2xl text-body-sm text-ink-2">{lead}</p>}
    </header>
  );
}
