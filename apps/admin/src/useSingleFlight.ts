import { useCallback, useRef } from "react";

/**
 * Run an action once at a time. A mutation's isPending only flips after a
 * re-render, so two quick clicks on "Export and freeze" could both go out;
 * a ref closes that window. Errors are the mutation's to report.
 */
export function useSingleFlight(): (run: () => Promise<unknown>) => Promise<void> {
  const flying = useRef(false);
  return useCallback(async (run) => {
    if (flying.current) return;
    flying.current = true;
    try {
      await run();
    } catch {
      // reported by the mutation's own state
    } finally {
      flying.current = false;
    }
  }, []);
}
