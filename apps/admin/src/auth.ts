/**
 * Who the arbiter is, and how they got here.
 *
 * Two ways in, decided by what the API says at /api/auth/config: an OIDC
 * authorization-code flow against the issuer (Zitadel), or -- only when the
 * API runs with dev auth -- a bare token typed into a field. The credential
 * the API client attaches is read synchronously from here, so the OIDC user
 * is mirrored into module state as oidc-client-ts loads and renews it.
 */

import type { Credential } from "@rochade/api-client";
import { UserManager, WebStorageStateStore, type User } from "oidc-client-ts";

export interface AuthConfig {
  issuer: string;
  client_id: string;
  dev_auth: boolean;
}

export type Account =
  | { kind: "dev"; subject: string }
  | { kind: "oidc"; subject: string; name: string };

export interface Session {
  config: AuthConfig;
  manager: UserManager | null;
  account: Account | null;
}

const TOKEN_KEY = "rochade.staff-token";
const RETURN_KEY = "rochade.return-to";

let oidcUser: User | null = null;

// --- the bare token, for dev auth ------------------------------------------

export function staffToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function signInWithToken(token: string): Account {
  localStorage.setItem(TOKEN_KEY, token);
  return { kind: "dev", subject: token };
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// --- what the API client sends ---------------------------------------------

export function currentCredential(): Credential | null {
  const token = staffToken();
  if (token) return { kind: "staff", token };
  if (oidcUser?.access_token && !oidcUser.expired) {
    return { kind: "staff", token: oidcUser.access_token };
  }
  return null;
}

// --- the OIDC side ---------------------------------------------------------

export function origin(): string {
  return window.location.origin;
}

export function createManager(config: AuthConfig): UserManager {
  const manager = new UserManager({
    authority: config.issuer,
    client_id: config.client_id,
    redirect_uri: `${origin()}/admin/callback`,
    post_logout_redirect_uri: `${origin()}/admin/`,
    response_type: "code",
    scope: "openid profile email offline_access",
    // Renew with the refresh token before the access token runs out, so a
    // round that lasts four hours does not end in a redirect mid-dispute.
    automaticSilentRenew: true,
    loadUserInfo: false,
    userStore: new WebStorageStateStore({ store: localStorage }),
  });
  manager.events.addUserLoaded((user) => {
    oidcUser = user;
  });
  manager.events.addUserUnloaded(() => {
    oidcUser = null;
  });
  return manager;
}

function accountOf(user: User): Account {
  const profile = user.profile;
  const name =
    (profile.name as string | undefined) ||
    (profile.preferred_username as string | undefined) ||
    (profile.email as string | undefined) ||
    profile.sub;
  return { kind: "oidc", subject: profile.sub, name };
}

/** Read the config and whatever credential is already held. */
export async function startSession(
  fetchConfig: () => Promise<AuthConfig>,
  manager: UserManager | null = null,
): Promise<Session> {
  const config = await fetchConfig();
  const token = staffToken();
  if (token && config.dev_auth) {
    return { config, manager, account: { kind: "dev", subject: token } };
  }
  if (token) clearToken();
  if (!config.issuer) return { config, manager: null, account: null };

  const held = manager ?? createManager(config);
  const user = await held.getUser();
  if (user && !user.expired) {
    oidcUser = user;
    return { config, manager: held, account: accountOf(user) };
  }
  if (user) {
    // Expired with a refresh token: renew now rather than bounce to the login.
    try {
      const renewed = await held.signinSilent();
      if (renewed) {
        oidcUser = renewed;
        return { config, manager: held, account: accountOf(renewed) };
      }
    } catch {
      await held.removeUser();
    }
  }
  return { config, manager: held, account: null };
}

export async function signInWithIssuer(manager: UserManager, returnTo: string): Promise<void> {
  sessionStorage.setItem(RETURN_KEY, returnTo);
  await manager.signinRedirect();
}

let redeeming: Promise<{ account: Account; returnTo: string }> | null = null;

/** Finish the redirect: exchange the code, then say where the arbiter was going. */
export function completeSignIn(
  manager: UserManager,
): Promise<{ account: Account; returnTo: string }> {
  // One exchange per code: React's development mode runs effects twice, and
  // the issuer rightly refuses a code the second time.
  redeeming ??= (async () => {
    const user = await manager.signinCallback();
    if (!user) throw new Error("the sign-in did not return a user");
    oidcUser = user;
    const returnTo = sessionStorage.getItem(RETURN_KEY) || "/";
    sessionStorage.removeItem(RETURN_KEY);
    return { account: accountOf(user), returnTo };
  })().finally(() => {
    redeeming = null;
  });
  return redeeming;
}

export async function signOut(session: Session): Promise<void> {
  clearToken();
  if (session.account?.kind === "oidc" && session.manager) {
    oidcUser = null;
    await session.manager.signoutRedirect();
  }
}

/** The API said 401: drop what we hold so the next screen is the sign-in. */
export async function forget(session: Session): Promise<void> {
  clearToken();
  oidcUser = null;
  if (session.manager) await session.manager.removeUser();
}

/** Test seam. */
export function _setOidcUser(user: User | null): void {
  oidcUser = user;
}
