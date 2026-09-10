/**
 * The small vocabulary every screen is built from. Buttons come in a few
 * weights and nothing else; a card is a card. Keeping this short is what keeps
 * the screens looking like one app.
 *
 * The look is design/admin/DESIGN.md: hairline borders instead of shadows,
 * 4px controls in 8px containers, cobalt for the one thing to press.
 */

import {
  forwardRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { Link } from "react-router";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export type Tone = "primary" | "dark" | "secondary" | "danger" | "ghost" | "success";

const BUTTON: Record<Tone, string> = {
  primary: "bg-accent text-white hover:bg-accent-strong disabled:bg-ink-3",
  dark: "bg-ink text-on-ink hover:bg-ink/85 disabled:bg-ink-3",
  success: "bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-emerald-300",
  danger: "bg-state-disputed text-white hover:bg-rose-700 disabled:bg-rose-300",
  secondary:
    "border border-line bg-card text-ink hover:border-line-strong hover:bg-subtle disabled:text-ink-3 disabled:hover:bg-card",
  ghost: "text-ink-2 hover:bg-subtle hover:text-ink disabled:text-ink-3",
};

const SIZE = {
  sm: "min-h-9 px-3 text-xs lg:min-h-8",
  md: "min-h-11 px-4 text-sm lg:min-h-9",
  lg: "min-h-12 px-5 text-sm",
} as const;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: Tone;
  size?: keyof typeof SIZE;
  busy?: boolean;
  /** A 16px Lucide glyph before the label. */
  icon?: ReactNode;
  /** Render as a router link instead of a button. */
  to?: string;
  state?: unknown;
};

export function Button({
  tone = "secondary",
  size = "md",
  className,
  busy,
  icon,
  children,
  to,
  state,
  ...rest
}: ButtonProps) {
  const classes = cx(
    "inline-flex items-center justify-center gap-1.5 rounded font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed [&>svg]:size-4 [&>svg]:shrink-0",
    SIZE[size],
    BUTTON[tone],
    className,
  );
  if (to !== undefined) {
    return (
      <Link to={to} state={state} className={classes} onClick={rest.onClick as never}>
        {icon}
        {children}
      </Link>
    );
  }
  return (
    <button
      type="button"
      {...rest}
      disabled={rest.disabled || busy}
      aria-busy={busy || undefined}
      className={classes}
    >
      {busy ? <Spinner /> : icon}
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
  return <Tag className={cx("rounded-lg border border-line bg-card", className)}>{children}</Tag>;
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
    <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line px-4 py-3 sm:px-5">
      <h2 className="text-headline-sm">{title}</h2>
      {aside && <p className="text-body-sm text-ink-2">{aside}</p>}
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
      <span className="font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="text-body-sm text-ink-3">{hint}</span>}
    </label>
  );
}

const CONTROL =
  "min-h-11 rounded border border-line bg-card px-3 text-base text-ink placeholder:text-ink-3 transition-colors hover:border-line-strong focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:bg-subtle lg:min-h-9 lg:text-sm";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...rest }, ref) {
    return <input ref={ref} {...rest} className={cx(CONTROL, className)} />;
  },
);

export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...rest} className={cx(CONTROL, className)} />;
}

/** A keycap, for the hotkey hints. */
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded-sm border border-line bg-card px-1.5 py-0.5 font-mono text-[10px] font-bold text-ink">
      {children}
    </kbd>
  );
}

/** Placeholder rows for the first load only. A background refetch never shows one. */
export function Skeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div role="status" aria-label="loading" className={cx("flex flex-col gap-2 p-4", className)}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-10 animate-pulse rounded bg-subtle" />
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
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-line-strong p-8 text-center">
      <p className="font-semibold">{title}</p>
      {children && <p className="max-w-md text-body-sm text-ink-2">{children}</p>}
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
    info: "border-line bg-subtle text-ink-2",
    warn: "border-amber-line bg-amber-soft text-amber-text",
    error: "border-rose-line bg-rose-soft text-rose-text",
    success: "border-emerald-line bg-emerald-soft text-emerald-text",
  }[tone];
  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className={cx("rounded-lg border px-4 py-3 text-sm [overflow-wrap:anywhere]", style, className)}
    >
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
        "inline-flex size-9 shrink-0 animate-pop items-center justify-center rounded-full bg-state-confirmed text-white",
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
