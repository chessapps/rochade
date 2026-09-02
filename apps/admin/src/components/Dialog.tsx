/**
 * A native <dialog>, opened modally: the browser traps focus, closes on Esc
 * and stacks it above everything. Nothing here re-implements any of that.
 */

import { useEffect, useRef, type ReactNode } from "react";

import { Button, cx } from "./ui";

export function Dialog({
  open,
  onClose,
  title,
  children,
  footer,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        // A click on the backdrop lands on the dialog element itself.
        if (event.target === event.currentTarget) onClose();
      }}
      className={cx(
        "m-auto w-[calc(100vw-2rem)] rounded-2xl bg-white p-0 text-ink shadow-xl backdrop:bg-slate-900/45",
        wide ? "max-w-2xl" : "max-w-md",
      )}
    >
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <h2 className="px-5 pt-5 text-lg font-semibold">{title}</h2>
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
  busy,
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
      onClose={busy ? () => undefined : onClose}
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
