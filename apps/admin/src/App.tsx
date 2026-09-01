import { useCallback, useEffect, useState } from "react";

import {
  api,
  errorDetails,
  errorMessage,
  signIn,
  signOut,
  staffToken,
  type ArbiterQueue,
  type DeviceSummary,
  type ImportPlan,
  type ManagerSummary,
  type RoundSummary,
  type TournamentDetail,
  type TournamentSummary,
} from "./api";
import {
  DevicePanel,
  FreezeWarning,
  ImportPanel,
  QueuePanel,
  SectionPanel,
  SignIn,
} from "./views";

export function App() {
  const [token, setToken] = useState(staffToken());
  const [tournaments, setTournaments] = useState<TournamentSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<TournamentDetail | null>(null);
  const [queue, setQueue] = useState<ArbiterQueue | null>(null);
  const [devices, setDevices] = useState<DeviceSummary[]>([]);

  const [managers, setManagers] = useState<ManagerSummary[]>([]);
  const [manager, setManager] = useState("vega");
  const [section, setSection] = useState("A");
  const [content, setContent] = useState("");
  const [filename, setFilename] = useState("");
  const [plan, setPlan] = useState<ImportPlan | null>(null);
  const [exporting, setExporting] = useState<RoundSummary | null>(null);
  const [issued, setIssued] = useState<
    { label: string; qr_payload: string; token: string } | null
  >(null);

  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadManagers = useCallback(async () => {
    const { data } = await api.GET("/api/managers");
    if (data) setManagers(data);
  }, []);

  const loadTournaments = useCallback(async () => {
    const { data, error } = await api.GET("/api/tournaments");
    if (error) return setProblem(errorMessage(error));
    setTournaments(data ?? []);
    if (!selected && data && data.length > 0) setSelected(data[0]!.id);
  }, [selected]);

  const loadTournament = useCallback(async (id: string) => {
    const [detailResult, queueResult, deviceResult] = await Promise.all([
      api.GET("/api/tournaments/{tournament_id}", {
        params: { path: { tournament_id: id } },
      }),
      api.GET("/api/tournaments/{tournament_id}/queue", {
        params: { path: { tournament_id: id }, query: { include_confirmed: false } },
      }),
      api.GET("/api/tournaments/{tournament_id}/devices", {
        params: { path: { tournament_id: id } },
      }),
    ]);
    if (detailResult.data) setDetail(detailResult.data);
    if (queueResult.data) setQueue(queueResult.data);
    if (deviceResult.data) setDevices(deviceResult.data);
  }, []);

  useEffect(() => {
    if (token) {
      void loadTournaments();
      void loadManagers();
    }
  }, [token, loadTournaments, loadManagers]);

  useEffect(() => {
    if (selected) void loadTournament(selected);
  }, [selected, loadTournament]);

  if (!token) {
    return (
      <SignIn
        onSignIn={(value) => {
          signIn(value);
          setToken(value);
        }}
      />
    );
  }

  const run = async (what: () => Promise<string | null>) => {
    setBusy(true);
    setProblem(null);
    try {
      const message = await what();
      if (message) setNotice(message);
      if (selected) await loadTournament(selected);
    } finally {
      setBusy(false);
    }
  };

  const preview = () =>
    run(async () => {
      if (!selected || !content) {
        setProblem("choose a file first");
        return null;
      }
      const { data, error } = await api.POST(
        "/api/tournaments/{tournament_id}/imports/preview",
        {
          params: { path: { tournament_id: selected } },
          body: { section_name: section, content, manager, force: true },
        },
      );
      if (error) {
        setProblem(errorMessage(error));
        return null;
      }
      setPlan(data ?? null);
      return null;
    });

  const commitImport = (force: boolean) =>
    run(async () => {
      if (!selected) return null;
      const { data, error } = await api.POST("/api/tournaments/{tournament_id}/imports", {
        params: { path: { tournament_id: selected } },
        body: { section_name: section, content, filename, manager, force },
      });
      if (error) {
        setProblem(errorMessage(error));
        return null;
      }
      setPlan(null);
      setContent("");
      return `Round ${data?.round_number} imported: ${data?.boards} boards.`;
    });

  const release = (round: RoundSummary) =>
    run(async () => {
      const ready = round.empty === 0 && round.disputed === 0;
      if (!ready) {
        const proceed = window.confirm(
          `Round ${round.number} still has ${round.empty} board(s) with no result and ` +
            `${round.disputed} disputed. Release anyway? This is recorded as forced.`,
        );
        if (!proceed) return null;
      }
      const { data, error } = await api.POST("/api/rounds/{round_id}/release", {
        params: { path: { round_id: round.id } },
        body: { force: !ready, note: "" },
      });
      if (error) {
        const details = errorDetails(error);
        setProblem(`${errorMessage(error)} ${JSON.stringify(details)}`);
        return null;
      }
      return `Round ${data?.round_number} released: ${data?.confirmed} results confirmed.`;
    });

  const runExport = (round: RoundSummary) =>
    run(async () => {
      const { data, error } = await api.POST("/api/rounds/{round_id}/export", {
        params: { path: { round_id: round.id } },
        body: { force: false },
      });
      setExporting(null);
      if (error) {
        setProblem(errorMessage(error));
        return null;
      }
      if (data) download(data.filename, data.content);
      return (
        `Exported ${data?.filename}. Round ${round.number} is frozen — ` +
        `load it into ${data?.manager ?? "the manager"} next.`
      );
    });

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">Seebach</h1>
        <select
          value={selected ?? ""}
          onChange={(event) => setSelected(event.target.value || null)}
          className="rounded-lg border border-slate-300 px-3 py-2"
        >
          {tournaments.map((tournament) => (
            <option key={tournament.id} value={tournament.id}>
              {tournament.name}
            </option>
          ))}
        </select>
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => {
            signOut();
            setToken(null);
          }}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          Sign out
        </button>
      </header>

      {problem && (
        <p className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-2 text-sm text-rose-900">
          {problem}
        </p>
      )}
      {notice && (
        <p className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm text-emerald-900">
          {notice}{" "}
          <button type="button" onClick={() => setNotice(null)} className="underline">
            dismiss
          </button>
        </p>
      )}

      {detail && (
        <SectionPanel
          detail={detail}
          busy={busy}
          onRelease={(round) => void release(round)}
          onExport={(round) => setExporting(round)}
        />
      )}

      <ImportPanel
        plan={plan}
        section={section}
        onSection={setSection}
        managers={managers}
        manager={manager}
        onManager={setManager}
        onFile={(file) => {
          setFilename(file.name);
          void file.text().then(setContent);
        }}
        onPreview={() => void preview()}
        onImport={(force) => void commitImport(force)}
        onCancel={() => setPlan(null)}
        busy={busy}
      />

      {queue && (
        <QueuePanel
          queue={queue}
          busy={busy}
          onSet={(entry, white, black) =>
            void run(async () => {
              const { error } = await api.PUT("/api/games/{game_id}/result", {
                params: { path: { game_id: entry.game_id } },
                body: { white_result: white, black_result: black, note: "" },
              });
              if (error) setProblem(errorMessage(error));
              return null;
            })
          }
          onResolve={(entry, result) =>
            void run(async () => {
              const { error } = await api.POST("/api/games/{game_id}/resolve", {
                params: { path: { game_id: entry.game_id } },
                body: { result, note: "" },
              });
              if (error) setProblem(errorMessage(error));
              return null;
            })
          }
        />
      )}

      <DevicePanel
        devices={devices}
        busy={busy}
        issued={issued}
        onDismissIssued={() => setIssued(null)}
        onIssue={(label) =>
          void run(async () => {
            if (!selected) return null;
            const { data, error } = await api.POST(
              "/api/tournaments/{tournament_id}/devices",
              {
                params: { path: { tournament_id: selected } },
                body: { label, base_url: window.location.origin },
              },
            );
            if (error) {
              setProblem(errorMessage(error));
              return null;
            }
            if (data) {
              setIssued({
                label: data.label,
                qr_payload: data.qr_payload,
                token: data.token,
              });
            }
            return null;
          })
        }
        onRevoke={(device) =>
          void run(async () => {
            const { error } = await api.DELETE("/api/devices/{device_id}", {
              params: { path: { device_id: device.id } },
            });
            if (error) setProblem(errorMessage(error));
            return null;
          })
        }
      />

      {exporting && (
        <FreezeWarning
          round={exporting}
          onConfirm={() => void runExport(exporting)}
          onCancel={() => setExporting(null)}
        />
      )}
    </div>
  );
}

/**
 * The export is a file the arbiter hands to Vega, so it has to leave the
 * browser as one. Held in memory only: it is never written anywhere we would
 * then have to keep in step with the round state.
 */
function download(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
