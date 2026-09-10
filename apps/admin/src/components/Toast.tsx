/**
 * Transient confirmations and failures, bottom of the screen, gone by
 * themselves. Anything the arbiter has to act on is not a toast.
 */

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

import { cx } from "./ui";

type Tone = "success" | "error" | "info";

interface Toast {
  id: number;
  tone: Tone;
  text: string;
}

interface ToastApi {
  success: (text: string) => void;
  error: (text: string) => void;
  info: (text: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TTL: Record<Tone, number> = { success: 4_000, info: 5_000, error: 8_000 };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);

  const push = useCallback((tone: Tone, text: string) => {
    const id = next.current++;
    setToasts((current) => [...current.slice(-3), { id, tone, text }]);
    window.setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), TTL[tone]);
  }, []);

  const value = useMemo<ToastApi>(
    () => ({
      success: (text) => push("success", text),
      error: (text) => push("error", text),
      info: (text) => push("info", text),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role={toast.tone === "error" ? "alert" : "status"}
            className={cx(
              "pointer-events-auto max-w-lg animate-pop rounded px-4 py-3 text-sm font-medium shadow-dock",
              toast.tone === "success" && "bg-emerald-600 text-white",
              toast.tone === "error" && "bg-state-disputed text-white",
              toast.tone === "info" && "bg-ink text-on-ink",
            )}
            onClick={() => setToasts((current) => current.filter((t) => t.id !== toast.id))}
          >
            {toast.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast outside ToastProvider");
  return api;
}
