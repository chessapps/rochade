/**
 * An arbiter with no password at all: invited, a passkey registered from the
 * link, and signed in to the app with nothing but that passkey.
 *
 * Drives the running stack like login_flow.mjs, but starts by creating a
 * throwaway account through Zitadel's API (the setup machine user's PAT) and
 * removes it at the end. The browser gets a virtual authenticator, so no
 * fingerprint reader is involved.
 *
 *     ZITADEL_PAT=... node scripts/passkey_flow.mjs [http://localhost:8092]
 *
 * The PAT is the file zitadel_setup reads: /zitadel/bootstrap/setup.pat in
 * the compose stack (docker compose exec zitadel cat /zitadel/bootstrap/setup.pat).
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE = process.argv[2] ?? "http://localhost:8092";
const PAT = process.env.ZITADEL_PAT;
if (!PAT) throw new Error("ZITADEL_PAT is required");
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SHOTS = path.join(ROOT, "scripts", "out");
const failures = [];
mkdirSync(SHOTS, { recursive: true });
function check(label, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${ok ? "" : " -- " + detail}`);
  if (!ok) failures.push(label);
}

const config = await (await fetch(BASE + "/api/auth/config")).json();
check("the API names an issuer", Boolean(config.issuer), JSON.stringify(config));
const ISSUER = config.issuer;

async function zitadel(method, route, body) {
  const res = await fetch(ISSUER + route, {
    method,
    headers: { Authorization: `Bearer ${PAT}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${route} -> ${res.status} ${text}`);
  return text ? JSON.parse(text) : {};
}

// 1. A throwaway arbiter, verified email, no password.
const stamp = Date.now();
const org = (await zitadel("POST", "/v2/organizations/_search", {})).result[0];
const created = await zitadel("POST", "/v2/users/human", {
  organization: { orgId: org.id },
  username: `passkey-${stamp}@example.invalid`,
  profile: { givenName: "Pia", familyName: "Passkey" },
  email: { email: `passkey-${stamp}@example.invalid`, isVerified: true },
});
const userId = created.userId;
check("an account is created without a password", Boolean(userId));

try {
  // 2. The registration link an invitation email would carry.
  const link = await zitadel("POST", `/v2/users/${userId}/passkeys/registration_link`, { returnCode: {} });
  const url =
    `${ISSUER}/ui/v2/login/passkey/set?userId=${userId}` +
    `&code=${encodeURIComponent(link.code.code)}&codeId=${link.code.id}&organization=${org.id}`;
  check("a passkey registration code is issued", Boolean(link.code?.code));

  // 3. A browser with a built-in authenticator registers the passkey.
  const browser = await chromium.launch({ channel: process.env.ROCHADE_BROWSER ?? "msedge", headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => check("no page error", false, e.message));
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: {
      protocol: "ctap2",
      transport: "internal",
      hasResidentKey: true,
      hasUserVerification: true,
      isUserVerified: true,
      automaticPresenceSimulation: true,
    },
  });

  await page.goto(url, { waitUntil: "networkidle" });
  // With a code in the link the page registers on its own; older builds
  // wait for a click. Either way the account ends up with one passkey.
  let passkeys = { result: [] };
  for (let i = 0; i < 15 && (passkeys.result ?? []).length === 0; i++) {
    const go = page.getByRole("button", { name: /continue|weiter|register|passkey/i }).first();
    if (await go.isVisible().catch(() => false)) await go.click().catch(() => {});
    await page.waitForTimeout(1000);
    passkeys = await zitadel("POST", `/v2/users/${userId}/passkeys/_search`, {});
  }
  await page.screenshot({ path: path.join(SHOTS, "passkey-1-registered.png") });
  check("the passkey is registered on the account", (passkeys.result ?? []).length === 1, JSON.stringify(passkeys));

  // 4. Into the app with the passkey alone: no password exists to type. The
  // registration left a Zitadel session behind; drop it so this is a real
  // sign-in, on the same page because the virtual authenticator lives there.
  await ctx.clearCookies();
  await page.goto(BASE + "/admin/?all", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((u) => u.href.startsWith(ISSUER), { timeout: 30_000 });
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline && !page.url().startsWith(BASE + "/admin")) {
    const box = page.getByRole("textbox").first();
    if (await box.isVisible().catch(() => false)) {
      await box.fill(`passkey-${stamp}@example.invalid`);
      await page.keyboard.press("Enter");
      await page.waitForTimeout(1500);
      continue;
    }
    const go = page.getByRole("button", { name: /passkey|continue|weiter|sign in|anmelden/i }).first();
    if (await go.isVisible().catch(() => false)) await go.click().catch(() => {});
    await page.waitForTimeout(1000);
  }
  if (!page.url().startsWith(BASE + "/admin")) {
    await page.screenshot({ path: path.join(SHOTS, "passkey-stuck.png") });
    check(
      "the passkey sign-in reaches the app",
      false,
      `${page.url()} :: ${(await page.locator("body").innerText()).slice(0, 400).replace(/\s+/g, " ")}`,
    );
  }
  await page.waitForURL((u) => u.href.startsWith(BASE + "/admin"), { timeout: 15_000 });
  const named = await page
    .getByText("Pia Passkey")
    .waitFor({ timeout: 15_000 })
    .then(() => true)
    .catch(() => false);
  await page.screenshot({ path: path.join(SHOTS, "passkey-2-signed-in.png") });
  check(
    "signed in to the app with the passkey only, no password on the account",
    named,
    `${page.url()} :: ${(await page.locator("body").innerText()).slice(0, 300).replace(/\s+/g, " ")}`,
  );
  await browser.close();
} finally {
  await zitadel("DELETE", `/v2/users/${userId}`);
  check("the throwaway account is removed again", true);
}

if (failures.length) {
  console.log(`\n${failures.length} check(s) failed`);
  process.exit(1);
}
console.log("\nan arbiter without a password gets in with a passkey");
