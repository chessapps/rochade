/**
 * An arbiter signs in through Zitadel, in a real browser, and gets work done.
 *
 * Like admin_flow.mjs this drives the running compose stack, but it starts
 * with no credential at all: the sign-in button, Zitadel's login page, the
 * first arbiter account from the env file, back through /admin/callback, a
 * tournament created with the token the issuer handed out, and sign-out.
 *
 *     docker compose up -d --build
 *     node scripts/login_flow.mjs [http://localhost:8092]
 *
 * ZITADEL_ADMIN_EMAIL / ZITADEL_ADMIN_PASSWORD override the compose defaults.
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE = process.argv[2] ?? "http://localhost:8092";
const EMAIL = process.env.ZITADEL_ADMIN_EMAIL ?? "admin@seebach.localhost";
const PASSWORD = process.env.ZITADEL_ADMIN_PASSWORD ?? "Password1!";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SHOTS = path.join(ROOT, "scripts", "out");
const failures = [];
mkdirSync(SHOTS, { recursive: true });
function check(label, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${ok ? "" : " -- " + detail}`);
  if (!ok) failures.push(label);
}

const config = await (await fetch(BASE + "/api/auth/config")).json();
check("the API names an issuer", Boolean(config.issuer && config.client_id), JSON.stringify(config));

const browser = await chromium.launch({ channel: process.env.SEEBACH_BROWSER ?? "msedge", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
page.on("pageerror", (e) => check("no page error", false, e.message));

// 1. No credential: the sign-in screen, then off to the issuer.
await page.goto(BASE + "/admin/t/nowhere/devices", { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Sign in", exact: true }).click();
await page.waitForURL((url) => url.href.startsWith(config.issuer), { timeout: 30_000 });
check("the sign-in button goes to the issuer", true);

// 2. Zitadel's login: name, then password. Skip whatever it offers to set up.
await page.getByRole("textbox").first().waitFor({ timeout: 30_000 });
await page.screenshot({ path: path.join(SHOTS, "login-1-issuer.png") });
await page.getByRole("textbox").first().fill(EMAIL);
await page.keyboard.press("Enter");
const password = page.locator('input[type="password"]');
await password.waitFor({ timeout: 30_000 });
await password.fill(PASSWORD);
await page.keyboard.press("Enter");
for (let i = 0; i < 5; i++) {
  if (page.url().startsWith(BASE)) break;
  const skip = page.getByRole("button", { name: /skip/i });
  if (await skip.isVisible().catch(() => false)) {
    await skip.click();
    continue;
  }
  await page.waitForTimeout(1000);
}
await page.waitForURL((url) => url.href.startsWith(BASE + "/admin/"), { timeout: 30_000 });

// 3. Back in the app, where the arbiter was going, as who they are.
await page.waitForURL(/\/admin\/t\/nowhere\/devices/, { timeout: 30_000 });
check("the callback returns to where the arbiter was going", true);
await page.getByText("Chief Arbiter").waitFor({ timeout: 15_000 });
check("the header names the account", true);
await page.screenshot({ path: path.join(SHOTS, "login-2-signed-in.png") });

// 4. The token the issuer gave out is a staff account to the API. (?all keeps
// the list from jumping straight to a sole tournament from an earlier run.)
await page.goto(BASE + "/admin/?all", { waitUntil: "networkidle" });
await page.getByRole("button", { name: "New tournament" }).first().click();
await page.getByRole("textbox", { name: "Name" }).fill(`Login Open ${Date.now()}`);
await page.getByRole("button", { name: "Create", exact: true }).click();
await page.waitForURL(/\/admin\/t\/[0-9a-f-]+$/, { timeout: 15_000 });
check("a tournament is created with the issuer's token", true);
const held = await page.evaluate(() => ({
  users: Object.keys(localStorage).filter((k) => k.startsWith("oidc.user:")).length,
  bare: localStorage.getItem("seebach.staff-token"),
}));
check("the session is held by oidc-client-ts, not as a bare token", held.users === 1 && !held.bare, JSON.stringify(held));

// 5. A second tab shares the session; no second login.
const other = await ctx.newPage();
await other.goto(BASE + "/admin/", { waitUntil: "networkidle" });
await other.getByText("Chief Arbiter").waitFor({ timeout: 15_000 });
check("a new tab is signed in already", true);
await other.close();

// 6. Sign out goes through the issuer and comes back signed out.
await page.getByRole("button", { name: "Sign out" }).click();
await page.waitForURL((url) => url.href.startsWith(BASE + "/admin/"), { timeout: 30_000 });
await page.getByRole("button", { name: "Sign in", exact: true }).waitFor({ timeout: 15_000 });
check("sign-out lands on the sign-in screen", true);
const leftover = await page.evaluate(() =>
  Object.keys(localStorage).filter((k) => k.startsWith("oidc.user:")).length,
);
check("nothing is held after sign-out", leftover === 0, `${leftover} user entries`);
await page.screenshot({ path: path.join(SHOTS, "login-3-signed-out.png") });

await browser.close();
if (failures.length) {
  console.log(`\n${failures.length} check(s) failed`);
  process.exit(1);
}
console.log("\nan arbiter signs in through Zitadel and out again");
