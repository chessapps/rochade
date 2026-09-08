import createClient from "openapi-fetch";
import type { paths } from "./schema";

export type { paths } from "./schema";

/**
 * Credentials come in two shapes and never mix: a staff OIDC bearer, and a
 * device token the app minted for one tournament and one playing day.
 */
export type Credential =
  | { kind: "staff"; token: string }
  | { kind: "device"; token: string };

export function authorization(credential: Credential): string {
  return credential.kind === "device"
    ? `Device ${credential.token}`
    : `Bearer ${credential.token}`;
}

export interface ApiOptions {
  /** Called when a request that carried a credential came back 401. */
  onUnauthorized?: () => void;
}

export function createApi(
  baseUrl: string,
  credential: () => Credential | null,
  options: ApiOptions = {},
) {
  return createClient<paths>({
    baseUrl,
    fetch: async (request) => {
      const held = credential();
      if (held) request.headers.set("Authorization", authorization(held));
      const response = await fetch(request);
      if (held && response.status === 401) options.onUnauthorized?.();
      return response;
    },
  });
}

export type Api = ReturnType<typeof createApi>;
