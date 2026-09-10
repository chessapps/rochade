/**
 * A native <dialog>, opened modally: the browser traps focus, closes on Esc
 * and stacks it above everything. Nothing here re-implements any of that.
 *
 * The one thing the browser does not know is that a mutation may be in
 * flight. While `busy`, Esc is refused and a close the browser forces anyway
 * is undone, so a failing release or export still has somewhere to show its
 * error.
 */

import { useEffect, useId, useRef, type ReactNode } from "react";

import { CircleAlert, Gavel, X } from "./icons";
import { Button, cx } from "./ui";

export type DialogTone = "default" | "danger" | "success";

export function Dialog({
  open,
  onClose,
  title,
  subtitle,
  tone = "default",
  children,
  footer,
  wide,
  busy = false,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  /** One line under the title, e.g. who is on the board. */
  subtitle?: ReactNode;
  tone?: DialogTone;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-busy={busy || undefined}
      onCancel={(event) => {
        if (busy) event.preventDefault();
      }}
      onClose={() => {
        // The browser closed it (Esc, or a close watcher that ignored the
        // cancel). If we are still busy, put it back and say nothing.
        if (busy && open) {
          ref.current?.showModal();
          return;
        }
        onClose();
      }}
      onClick={(event) => {
        // A click on the backdrop lands on the dialog element itself.
        if (event.target === event.currentTarget && !busy) onClose();
      }}
      className={cx(
        "m-auto w-[calc(100vw-2rem)] rounded-lg border border-line bg-card p-0 text-ink shadow-xl backdrop:backdrop-blur-[2px]",
        wide ? "max-w-2xl" : "max-w-md",
      )}
    >
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <div className="flex items-start gap-3 border-b border-line px-5 py-4">
            {tone !== "default" && (
              <span
                aria-hidden
                className={cx(
                  "flex size-8 shrink-0 items-center justify-center rounded [&>svg]:size-4",
                  tone === "danger" ? "bg-rose-soft text-rose-text" : "bg-emerald-soft text-emerald-text",
                )}
              >
                {tone === "danger" ? <Gavel /> : <CircleAlert />}
              </span>
            )}
            <div className="min-w-0 flex-1">
              <h2 id={titleId} className="text-headline-sm">
                {title}
              </h2>
              {subtitle && <p className="text-body-sm text-ink-2">{subtitle}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              aria-label="Close"
              className="-mr-1 rounded p-1 text-ink-3 hover:bg-subtle hover:text-ink-2 disabled:opacity-40 [&>svg]:size-4"
            >
              <X />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-sm text-ink-2">{children}</div>
          {footer && (
            <div className="flex flex-wrap justify-end gap-2 border-t border-line bg-subtle px-5 py-3">
              {footer}
            </div>
          )}
        </div>
      )}
    </dialog>
  );
}

/**
 * Yes/no with a consequence spelled out. The confirm button is disabled while
 * the action runs, so a double click cannot run it twice.
 */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  subtitle,
  confirmLabel,
  tone = "primary",
  busy = false,
  children,
  disabled,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  confirmLabel: string;
  tone?: "primary" | "danger" | "success";
  busy?: boolean;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      busy={busy}
      title={title}
      subtitle={subtitle}
      tone={tone === "primary" ? "default" : tone}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button tone={tone} onClick={onConfirm} busy={busy} disabled={disabled}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
    </Dialog>
  );
}
