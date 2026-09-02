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

import { Button, cx } from "./ui";

export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
  wide,
  busy = false,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
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
        "m-auto w-[calc(100vw-2rem)] rounded-2xl bg-white p-0 text-ink shadow-xl backdrop:bg-slate-900/45",
        wide ? "max-w-2xl" : "max-w-md",
      )}
    >
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <h2 id={titleId} className="px-5 pt-5 text-lg font-semibold">
            {title}
          </h2>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-sm text-slate-700">
            {children}
          </div>
          {footer && (
            <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-5 py-4">
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
