/**
 * The pieces a guide page is built from: numbered steps, files, notes, menu
 * paths. One look for every program's guide.
 */

import { Fragment, type ReactNode } from "react";

import { Card, Kbd } from "./ui";

export { Kbd };

/** The loop in one picture: where each file comes from and where it goes. */
export function Loop({
  cells,
}: {
  cells: { where: string; title: string; body: ReactNode }[];
}) {
  const cell = "flex flex-col gap-1 rounded-md border border-line bg-subtle/60 p-3";
  return (
    <Card className="p-4 sm:p-5">
      <h2 className="text-headline-sm">One round, in files</h2>
      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto_1fr_auto_1fr]">
        {cells.map((c, i) => (
          <Fragment key={c.title}>
            {i > 0 && (
              <span aria-hidden className="self-center font-mono text-ink-3">
                →
              </span>
            )}
            <div className={cell}>
              <span className="text-label-sm text-ink-3">{c.where}</span>
              <span className="font-semibold">{c.title}</span>
              <span className="text-body-sm text-ink-2">{c.body}</span>
            </div>
          </Fragment>
        ))}
      </div>
    </Card>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card as="section" className="flex flex-col gap-4 p-4 sm:p-5">
      <h2 className="text-headline-sm">{title}</h2>
      {children}
    </Card>
  );
}

export function Steps({ children }: { children: ReactNode }) {
  return <ol className="flex flex-col gap-5">{children}</ol>;
}

export function Step({ n, title, children }: { n?: number; title: string; children: ReactNode }) {
  return (
    <li className="grid gap-x-4 gap-y-2 sm:grid-cols-[2rem_1fr]">
      <span
        aria-hidden
        className="flex size-8 items-center justify-center rounded-full bg-ink font-mono text-sm font-bold text-on-ink"
      >
        {n ?? "·"}
      </span>
      <div className="min-w-0 text-body-md text-ink-2 [&>*+div]:mt-2 [&>*+p]:mt-2 [&>*+ul]:mt-2 [&>div+*]:mt-2 [&>p+*]:mt-2 [&>ul+*]:mt-2">
        <h3 className="mb-1 text-base font-semibold text-ink">{title}</h3>
        {children}
      </div>
    </li>
  );
}

export function Files({ children }: { children: ReactNode }) {
  return <ul className="flex flex-col gap-1.5">{children}</ul>;
}

export function File({ name, children }: { name: string; children: ReactNode }) {
  return (
    <li className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
      <Code>{name}</Code>
      <span className="text-body-sm text-ink-2">{children}</span>
    </li>
  );
}

export function Note({ tone = "plain", children }: { tone?: "plain" | "good" | "warn"; children: ReactNode }) {
  const tones = {
    plain: "border-line bg-subtle/60 text-ink-2",
    good: "border-emerald-line bg-emerald-soft text-emerald-text",
    warn: "border-amber-line bg-amber-soft text-amber-text",
  };
  return <div className={`rounded-md border px-3 py-2 text-body-sm ${tones[tone]}`}>{children}</div>;
}

export function Fact({ children }: { children: ReactNode }) {
  return <li className="border-l-2 border-line pl-3">{children}</li>;
}

/** A menu path in Vega, as it appears there. */
export function M({ children }: { children: ReactNode }) {
  return <span className="font-medium text-ink">{children}</span>;
}

export function Code({ children }: { children: ReactNode }) {
  return <span className="font-mono text-[0.92em] text-accent">{children}</span>;
}
