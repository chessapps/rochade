/**
 * Mount a screen the way main.tsx does, with the API stubbed.
 *
 * Tests hand in what the API should answer per (method, path prefix); anything
 * unexpected fails loudly rather than hanging a query forever.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router";

import { api } from "./api";
import { ToastProvider } from "./components/Toast";

export type Stub = (path: string, options?: { body?: unknown }) => unknown;

export interface Stubs {
  GET?: Record<string, unknown | ((path: string) => unknown)>;
  POST?: Record<string, unknown | Stub>;
  PUT?: Record<string, unknown | Stub>;
  DELETE?: Record<string, unknown | Stub>;
}

export interface Call {
  method: string;
  path: string;
  body?: unknown;
}

/** Point `api.GET`/`POST`/… at a table of answers; returns the calls made. */
export function stubApi(stubs: Stubs): Call[] {
  const calls: Call[] = [];
  for (const method of ["GET", "POST", "PUT", "DELETE"] as const) {
    vi.spyOn(api, method).mockImplementation((async (path: string, init?: { body?: unknown; params?: { path?: Record<string, string> } }) => {
      const resolved = path.replace(/\{(\w+)\}/g, (_, key: string) => init?.params?.path?.[key] ?? key);
      calls.push({ method, path: resolved, body: init?.body });
      const table = stubs[method] ?? {};
      const hit = Object.entries(table).find(([prefix]) => resolved === prefix || resolved.startsWith(prefix));
      if (!hit) {
        return { error: { message: `no stub for ${method} ${resolved}` }, response: new Response(null, { status: 500 }) };
      }
      const answer = await (typeof hit[1] === "function" ? (hit[1] as Stub)(resolved, init) : hit[1]);
      if (answer instanceof Error) {
        return { error: { message: answer.message }, response: new Response(null, { status: 409 }) };
      }
      return { data: answer, response: new Response(null, { status: 200 }) };
    }) as never);
  }
  return calls;
}

export function renderAt(path: string, route: string, element: ReactElement): RenderResult {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <Routes>
            <Route path={route} element={element} />
            <Route path="*" element={<p data-testid="elsewhere" />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
