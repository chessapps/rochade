import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router";

import { App } from "./App";
import { _setOidcUser } from "./auth";
import { ToastProvider } from "./components/Toast";
import { stubApi } from "./test-utils";

const oidc = vi.hoisted(() => ({
  getUser: vi.fn(),
  signinRedirect: vi.fn(),
  signinSilent: vi.fn(),
  signinCallback: vi.fn(),
  signoutRedirect: vi.fn(),
  removeUser: vi.fn(),
}));

vi.mock("oidc-client-ts", () => ({
  UserManager: vi.fn().mockImplementation(() => ({
    ...oidc,
    events: { addUserLoaded: vi.fn(), addUserUnloaded: vi.fn() },
  })),
  WebStorageStateStore: vi.fn(),
}));

const ISSUER = { issuer: "http://localhost:8093", client_id: "42@rochade", dev_auth: false };
const DEV = { issuer: "", client_id: "", dev_auth: true };
const BOTH = { ...ISSUER, dev_auth: true };

function mount(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider>
          <App />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  _setOidcUser(null);
  oidc.getUser.mockReset().mockResolvedValue(null);
  oidc.signinRedirect.mockReset().mockResolvedValue(undefined);
  oidc.signoutRedirect.mockReset().mockResolvedValue(undefined);
  oidc.removeUser.mockReset().mockResolvedValue(undefined);
});

describe("signing in", () => {
  it("takes a bare token when the API runs with dev auth", async () => {
    stubApi({ GET: { "/api/auth/config": DEV, "/api/tournaments": [] } });
    mount();
    const field = await screen.findByLabelText("staff token");
    expect(screen.queryByRole("button", { name: "Sign in" })).toBeDisabled();
    await userEvent.type(field, "arbiter-1{enter}");
    expect(await screen.findByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(localStorage.getItem("rochade.staff-token")).toBe("arbiter-1");
  });

  it("sends the arbiter to the issuer and remembers where they were going", async () => {
    stubApi({ GET: { "/api/auth/config": ISSUER } });
    mount("/t/t1/devices");
    await userEvent.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(oidc.signinRedirect).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("rochade.return-to")).toBe("/t/t1/devices");
    // No token field without dev auth.
    expect(screen.queryByLabelText("staff token")).not.toBeInTheDocument();
  });

  it("offers both when the API has an issuer and dev auth", async () => {
    stubApi({ GET: { "/api/auth/config": BOTH } });
    mount();
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByLabelText("staff token")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Use token" })).toBeInTheDocument();
  });

  it("says so when the API has neither", async () => {
    stubApi({ GET: { "/api/auth/config": { issuer: "", client_id: "", dev_auth: false } } });
    mount();
    expect(await screen.findByText(/not configured/)).toBeInTheDocument();
  });
});

describe("the callback", () => {
  it("redeems the code once and returns the arbiter to where they were going", async () => {
    sessionStorage.setItem("rochade.return-to", "/t/t1/devices");
    oidc.signinCallback.mockReset().mockResolvedValue({
      access_token: "jwt.jwt.jwt",
      expired: false,
      profile: { sub: "224466", name: "Anna Arbiter" },
    });
    stubApi({
      GET: {
        "/api/auth/config": ISSUER,
        "/api/tournaments/t1/devices": [],
        "/api/tournaments/t1": { id: "t1", name: "Test Open", sections: [] },
        "/api/tournaments": [],
      },
    });
    render(
      <StrictMode>
        <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
          <MemoryRouter initialEntries={["/callback?code=abc&state=xyz"]}>
            <ToastProvider>
              <App />
            </ToastProvider>
          </MemoryRouter>
        </QueryClientProvider>
      </StrictMode>,
    );
    expect(await screen.findByText("Phones in the hall")).toBeInTheDocument();
    expect(oidc.signinCallback).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("rochade.return-to")).toBeNull();
  });
});

describe("a held session", () => {
  it("shows the account from the issuer and signs out through it", async () => {
    oidc.getUser.mockResolvedValue({
      access_token: "jwt.jwt.jwt",
      expired: false,
      profile: { sub: "224466", name: "Anna Arbiter" },
    });
    stubApi({ GET: { "/api/auth/config": ISSUER, "/api/tournaments": [] } });
    mount();
    expect(await screen.findByText("Anna Arbiter")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(oidc.signoutRedirect).toHaveBeenCalledTimes(1));
  });

  it("drops a dev token the API no longer accepts", async () => {
    localStorage.setItem("rochade.staff-token", "stale");
    stubApi({ GET: { "/api/auth/config": ISSUER, "/api/tournaments": [] } });
    mount();
    // The API has an issuer and no dev auth, so the stale token is not a session.
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(localStorage.getItem("rochade.staff-token")).toBeNull();
  });
});
