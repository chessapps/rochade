/**
 * A place to drop the manager's files. Dashed until something is over it,
 * cobalt while it is, emerald once what it holds is enough. The input stays a
 * real file input, visually hidden, so a click and a screen reader both work.
 */

import { useState, type InputHTMLAttributes, type ReactNode } from "react";

import { Upload } from "./icons";
import { cx } from "./ui";

export function DropZone({
  onFiles,
  ready = false,
  title,
  hint,
  children,
  inputLabel,
  compact = false,
  className,
  ...input
}: Omit<InputHTMLAttributes<HTMLInputElement>, "onChange" | "className" | "title"> & {
  onFiles: (files: FileList | null) => void;
  /** Everything needed is here: show it green. */
  ready?: boolean;
  title: ReactNode;
  hint?: ReactNode;
  /** Anything to say under the hint, e.g. the file that was picked. */
  children?: ReactNode;
  inputLabel?: string;
  compact?: boolean;
  className?: string;
}) {
  const [over, setOver] = useState(false);
  return (
    <label
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        onFiles(event.dataTransfer.files);
      }}
      className={cx(
        "group flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 text-center transition-colors",
        compact ? "py-5" : "py-8",
        over
          ? "border-accent bg-accent-soft/40"
          : ready
            ? "border-emerald-line bg-emerald-soft"
            : "border-line-strong bg-subtle/50 hover:border-accent hover:bg-accent-soft/20",
        className,
      )}
    >
      <input
        type="file"
        {...input}
        aria-label={inputLabel}
        className="sr-only"
        onChange={(event) => onFiles(event.target.files)}
      />
      <span
        className={cx(
          "flex size-10 items-center justify-center rounded-full border bg-card transition-colors [&>svg]:size-5",
          ready
            ? "border-emerald-line text-state-confirmed"
            : "border-line text-ink-2 group-hover:border-accent group-hover:text-accent",
        )}
      >
        <Upload />
      </span>
      <span className="text-body-sm font-semibold text-ink group-hover:text-accent">{title}</span>
      {hint && <span className="text-body-sm text-ink-3">{hint}</span>}
      {children}
    </label>
  );
}
