import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ConfirmDialog } from "./Dialog";

describe("ConfirmDialog", () => {
  it("refuses Esc and undoes a forced close while the action is in flight", async () => {
    const onClose = vi.fn();
    render(
      <ConfirmDialog open busy onClose={onClose} onConfirm={() => undefined} title="Export" confirmLabel="Go">
        working
      </ConfirmDialog>,
    );
    const dialog = screen.getByRole("dialog", { hidden: true });
    const showModal = vi.spyOn(dialog as HTMLDialogElement, "showModal");

    const cancel = new Event("cancel", { cancelable: true });
    dialog.dispatchEvent(cancel);
    expect(cancel.defaultPrevented).toBe(true);

    // A close watcher that ignored the cancel: the dialog comes straight back.
    dialog.dispatchEvent(new Event("close"));
    expect(showModal).toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }).closest("button")!);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes normally when idle and names itself by its title", () => {
    const onClose = vi.fn();
    render(
      <ConfirmDialog open onClose={onClose} onConfirm={() => undefined} title="Release round 3" confirmLabel="Go">
        sure?
      </ConfirmDialog>,
    );
    const dialog = screen.getByRole("dialog", { hidden: true });
    expect(dialog).toHaveAccessibleName("Release round 3");
    dialog.dispatchEvent(new Event("close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
