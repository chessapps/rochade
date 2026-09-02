/**
 * The small vocabulary every screen is built from. Buttons come in three
 * weights and nothing else; a card is a card. Keeping this short is what keeps
 * the screens looking like one app.
 */

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

type Tone = "primary" | "secondary" | "danger" | "ghost" | "success";

const BUTTON: Record<Tone, string> = {
  primary: "bg-ink text-white hover:bg-slate-700 disabled:bg-slate-400",
  success: "bg-emerald-700 text-white hover:bg-emerald-600 disabled:bg-emerald-300",
  danger: "bg-rose-700 text-white hover:bg-rose-600 disabled:bg-rose-300",
  secondary:
    "border border-slate-300 bg-white text-ink hover:bg-slate-50 disabled:text-slate-400 disabled:hover:bg-white",
  ghost: "text-slate-600 hover:bg-slate-100 disabled:text-slate-400",
};

export function Button({
  tone = "secondary",
  size = "md",
  className,
  busy,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: Tone;
  size?: "sm" | "md" | "lg";
  busy?: boolean;
}) {
  return (
    <button
      type="button"
      {...rest}
      disabled={rest.disabled || busy}
      aria-busy={busy || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed",
        size === "sm" && "min-h-9 px-3 text-sm",
        size === "md" && "min-h-11 px-4 text-sm",
        size === "lg" && "min-h-12 px-5 text-base",
        BUTTON[tone],
        className,
      )}
    >
      {busy && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
    />
  );
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
  return (
    <Tag className={cx("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>
      {children}
    </Tag>
  );
}

export function CardHeader({
  title,
  aside,
  children,
}: {
  title: ReactNode;
  aside?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-slate-100 px-4 py-3 sm:px-5">
      <h2 className="text-base font-semibold">{title}</h2>
      {aside && <p className="text-sm text-slate-500">{aside}</p>}
      {children}
    </header>
  );
}

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={cx("flex flex-col gap-1 text-sm", className)}>
      <span className="font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

const CONTROL =
  "min-h-11 rounded-lg border border-slate-300 bg-white px-3 text-base text-ink placeholder:text-slate-400 disabled:bg-slate-50";

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...rest} className={cx(CONTROL, className)} />;
}

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...rest} className={cx(CONTROL, className)} />;
}

/** Placeholder rows for the first load only. A background refetch never shows one. */
export function Skeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div role="status" aria-label="loading" className={cx("flex flex-col gap-2 p-4", className)}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-lg bg-slate-100" />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-slate-300 p-8 text-center">
      <p className="font-medium">{title}</p>
      {children && <p className="max-w-md text-sm text-slate-500">{children}</p>}
      {action}
    </div>
  );
}

export function Banner({
  tone,
  children,
  className,
}: {
  tone: "info" | "warn" | "error" | "success";
  children: ReactNode;
  className?: string;
}) {
  const style = {
    info: "border-slate-200 bg-slate-50 text-slate-700",
    warn: "border-amber-300 bg-amber-50 text-amber-900",
    error: "border-rose-300 bg-rose-50 text-rose-900",
    success: "border-emerald-300 bg-emerald-50 text-emerald-950",
  }[tone];
  return (
    <div role={tone === "error" ? "alert" : undefined} className={cx("rounded-lg border px-4 py-3 text-sm [overflow-wrap:anywhere]", style, className)}>
      {children}
    </div>
  );
}

/** The check that appears once something irreversible has gone through. */
export function SuccessCheck({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-flex size-9 shrink-0 animate-pop items-center justify-center rounded-full bg-emerald-600 text-white",
        className,
      )}
    >
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="3">
        <path
          d="M5 12.5l4.5 4.5L19 7.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="48"
          className="animate-draw"
        />
      </svg>
    </span>
  );
}
