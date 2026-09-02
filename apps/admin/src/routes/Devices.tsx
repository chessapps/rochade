/**
 * The phones. Each QR admits one phone to this tournament for today; the
 * token behind it is shown once, here, and never again.
 */

import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { errorMessage, type DeviceSummary, type IssuedDevice } from "../api";
import { ConfirmDialog, Dialog } from "../components/Dialog";
import { QrCode } from "../components/QrCode";
import { DeviceChip } from "../components/StateChip";
import { useToast } from "../components/Toast";
import { Banner, Button, Card, CardHeader, EmptyState, Input, Skeleton } from "../components/ui";
import { clockTime, plural, relativeTime } from "../format";
import { useDevices, useIssueDevice, useRevokeDevice, useTournament } from "../queries";
import { useNow } from "../useNow";

export function Devices() {
  const { tournamentId = "" } = useParams();
  const tournament = useTournament(tournamentId);
  const devices = useDevices(tournamentId);
  const issue = useIssueDevice();
  const toast = useToast();
  const now = useNow(10_000);

  const [label, setLabel] = useState("");
  const [issued, setIssued] = useState<IssuedDevice | null>(null);
  const [revoking, setRevoking] = useState<DeviceSummary | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (issue.isPending) return;
    issue.mutate(
      { tournamentId, label: label.trim() },
      {
        onSuccess: (data) => {
          setIssued(data);
          setLabel("");
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  };

  const list = devices.data ?? [];
  const active = list.filter((d) => d.active);

  return (
    <div className="flex flex-col gap-4">
      <header>
        <Link to={`/t/${tournamentId}`} className="text-sm text-slate-500 hover:underline">
          ← {tournament.data?.name ?? "Tournament"}
        </Link>
        <h1 className="mt-1 text-xl font-semibold">Phones in the hall</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          A QR code admits one phone to this tournament for today. Print it as a poster for
          the hall, or hand it to a helper. Revoking is immediate, and every result the phone
          entered stays in the log.
        </p>
      </header>

      <Card className="p-4 sm:p-5">
        <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="flex flex-1 flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">Label</span>
            <Input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="e.g. poster by the door, or Anna's phone"
            />
          </label>
          <Button type="submit" tone="primary" size="lg" busy={issue.isPending}>
            Issue a QR code
          </Button>
        </form>
      </Card>

      <Card>
        <CardHeader
          title="Issued"
          aside={active.length > 0 ? `${plural(active.length, "phone")} can enter results` : undefined}
        />
        {devices.isPending ? (
          <Skeleton rows={3} />
        ) : devices.isError ? (
          <Banner tone="error" className="m-4">
            {errorMessage(devices.error)}
          </Banner>
        ) : list.length === 0 ? (
          <div className="p-4">
            <EmptyState title="No phones admitted yet">
              Issue a QR code above and let players scan it — or print it and put it up.
            </EmptyState>
          </div>
        ) : (
          <ul>
            {list.map((device) => (
              <li
                key={device.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-slate-100 px-4 py-3 text-sm sm:px-5"
              >
                <span className="min-w-0 flex-1 truncate font-medium">
                  {device.label || "unlabelled"}
                </span>
                <span className="text-slate-500 tabular-nums">
                  {device.last_seen_at
                    ? `last entry ${relativeTime(device.last_seen_at, now)}`
                    : "not used yet"}
                </span>
                <DeviceChip state={stateOf(device)} />
                {device.active ? (
                  <Button size="sm" tone="ghost" onClick={() => setRevoking(device)}>
                    Revoke
                  </Button>
                ) : (
                  <span className="w-[4.5rem]" />
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <IssuedDialog
        issued={issued}
        tournamentId={tournamentId}
        onClose={() => setIssued(null)}
      />
      <RevokeDialog device={revoking} tournamentId={tournamentId} onClose={() => setRevoking(null)} />
    </div>
  );
}

function stateOf(device: DeviceSummary): "active" | "expired" | "revoked" {
  if (device.active) return "active";
  return device.revoked_at ? "revoked" : "expired";
}

function IssuedDialog({
  issued,
  tournamentId,
  onClose,
}: {
  issued: IssuedDevice | null;
  tournamentId: string;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const toast = useToast();
  return (
    <Dialog
      open={issued !== null}
      onClose={onClose}
      title={issued?.label ? `QR code — ${issued.label}` : "QR code"}
      footer={
        <>
          <Button
            onClick={() =>
              issued &&
              navigate(`/t/${tournamentId}/devices/poster`, {
                state: { qr_payload: issued.qr_payload, label: issued.label, expires_at: issued.expires_at },
              })
            }
          >
            Open as a poster
          </Button>
          <Button tone="primary" onClick={onClose}>
            Done
          </Button>
        </>
      }
    >
      {issued && (
        <div className="flex flex-col items-center gap-3 text-center">
          <QrCode value={issued.qr_payload} />
          <p>
            Scan with the phone's camera. Valid until {clockTime(issued.expires_at)} today.
          </p>
          <Banner tone="warn" className="w-full text-left">
            Shown once. Close this and the code is gone — issue another if you need it again.
          </Banner>
          <button
            type="button"
            className="text-xs text-slate-500 underline-offset-2 hover:underline"
            onClick={() =>
              void navigator.clipboard
                .writeText(issued.qr_payload)
                .then(() => toast.info("Link copied."))
                .catch(() => toast.error("Could not copy."))
            }
          >
            copy the link instead
          </button>
        </div>
      )}
    </Dialog>
  );
}

function RevokeDialog({
  device,
  tournamentId,
  onClose,
}: {
  device: DeviceSummary | null;
  tournamentId: string;
  onClose: () => void;
}) {
  const revoke = useRevokeDevice();
  const toast = useToast();
  return (
    <ConfirmDialog
      open={device !== null}
      onClose={onClose}
      title={`Revoke ${device?.label || "this phone"}?`}
      confirmLabel="Revoke"
      tone="danger"
      busy={revoke.isPending}
      onConfirm={() =>
        device &&
        revoke.mutate(
          { deviceId: device.id, tournamentId },
          {
            onSuccess: () => {
              toast.success(`${device.label || "The phone"} can no longer enter results.`);
              onClose();
            },
            onError: (error) => toast.error(errorMessage(error)),
          },
        )
      }
    >
      <p>
        The phone stops working at once. Results it already entered stay where they are and in
        the log; a poster that carried this code is dead from now on.
      </p>
    </ConfirmDialog>
  );
}
