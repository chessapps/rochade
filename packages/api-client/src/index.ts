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

export function createApi(baseUrl: string, credential: () => Credential | null) {
  return createClient<paths>({
    baseUrl,
    fetch: (request) => {
      const held = credential();
      if (held) request.headers.set("Authorization", authorization(held));
      return fetch(request);
    },
  });
}

export type Api = ReturnType<typeof createApi>;
