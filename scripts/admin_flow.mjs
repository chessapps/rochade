/**
 * The arbiter's round, driven through the admin app in a real browser.
 *
 * Not part of the test suite: like scripts/smoke.py this exercises the running
 * compose stack, but through the screens rather than the API -- create a
 * tournament, import a round, watch claims arrive by polling, resolve a dispute,
 * set a result from the keyboard, release, export, download the file again,
 * import the next round, issue a QR, open the poster, revoke; then check that
 * nothing overflows at phone and tablet widths.
 *
 *     docker compose up -d --build
 *     node scripts/admin_flow.mjs [http://localhost:8080]
 *
 * Uses the browser already on the machine (SEEBACH_BROWSER, default msedge;
 * "chrome" works too) so nothing is downloaded. Playwright is a root
 * devDependency for this script alone.
 */
import { chromium } from "playwright";
import { mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const BASE = process.argv[2] ?? "http://localhost:8080";
const TOKEN = `flow-${Date.now()}`;
const staff = { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" };
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FIX = path.join(ROOT, "tests", "fixtures", "swiss_manager") + path.sep;
const SHOTS = path.join(ROOT, "scripts", "out");
const failures = [];
mkdirSync(SHOTS, { recursive: true });
function check(label, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${ok ? "" : " -- " + detail}`);
  if (!ok) failures.push(label);
}
async function api(method, path, body, headers = staff) {
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${text}`);
  return text ? JSON.parse(text) : null;
}

for (let i = 0; i < 60; i++) {
  try { if ((await fetch(BASE + "/api/managers", { headers: staff })).ok) break; } catch {}
  await new Promise((r) => setTimeout(r, 1000));
}
const browser = await chromium.launch({ channel: process.env.SEEBACH_BROWSER ?? "msedge", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
await ctx.addInitScript((tok) => localStorage.setItem("seebach.staff-token", tok), TOKEN);
const page = await ctx.newPage();
page.on("pageerror", (e) => check("no page error", false, e.message));

// 1. Create a tournament in the UI.
await page.goto(BASE + "/admin/", { waitUntil: "networkidle" });
await page.getByRole("button", { name: "New tournament" }).first().click();
await page.getByLabel("Name").fill("Flow Open");
await page.getByRole("button", { name: "Create", exact: true }).click();
await page.waitForURL(/\/admin\/t\/[0-9a-f-]+$/);
const tournamentId = page.url().split("/").pop();
await page.waitForSelector("text=No sections yet");
check("create tournament lands on its home", true);

// 2. Import round 3 through the wizard.
await page.getByRole("link", { name: "Import the paired round" }).click();
await page.waitForURL(/\/import/);
await page.getByLabel("Section").fill("A");
await page.setInputFiles('input[type="file"]', { name: "FIDE_Export_m0-seed.TXT", mimeType: "text/plain", buffer: Buffer.from(readFileSync(FIX + "round3_paired.trf")) });
await page.getByRole("button", { name: "Preview the changes" }).click();
await page.getByRole("button", { name: /Import round 3/ }).click();
await page.waitForURL(/\/rounds\//);
const roundId = page.url().split("/").pop();
await page.waitForSelector("text=Section A · Round 3");
check("import lands on the round board", true);
check("attention filter is the default while open", (await page.getByRole("tab", { name: /Attention/ }).getAttribute("aria-selected")) === "true");

// 3. Phones claim; one dispute. Watch the board update by polling.
const dev1 = await api("POST", `/api/tournaments/${tournamentId}/devices`, { label: "poster", base_url: BASE });
const dev2 = await api("POST", `/api/tournaments/${tournamentId}/devices`, { label: "Anna", base_url: BASE });
const phone = (d) => ({ Authorization: `Device ${d.token}`, "Content-Type": "application/json" });
const boards = (await api("GET", `/api/tournaments/${tournamentId}/boards`, null, phone(dev1))).boards.filter((b) => !b.is_bye);
await api("POST", `/api/games/${boards[0].game_id}/claim`, { result: "white_win" }, phone(dev1));
await api("POST", `/api/games/${boards[1].game_id}/claim`, { result: "draw" }, phone(dev2));
await api("POST", `/api/games/${boards[2].game_id}/claim`, { result: "white_win" }, phone(dev1));
await api("POST", `/api/games/${boards[2].game_id}/claim`, { result: "black_win" }, phone(dev2));
await page.waitForFunction(() => document.body.innerText.includes("Two phones disagree"), null, { timeout: 15000 });
check("a dispute arrives by polling", true);
check("the pulse class was applied", (await page.locator("li.animate-row-pulse").count()) > 0);
await page.waitForFunction(() => /“poster”/.test(document.body.innerText) && /“Anna”/.test(document.body.innerText), null, { timeout: 8000 });
check("the claims name the phones", true);

// 4. Resolve the dispute with a button, set the empty board with the keyboard.
const disputed = page.locator(`li[data-game-id="${boards[2].game_id}"]`);
await disputed.getByRole("button", { name: "½:½" }).click();
await page.waitForFunction((id) => !document.querySelector(`li[data-game-id="${id}"]`), boards[2].game_id, { timeout: 8000 });
check("a resolved board leaves the attention list", true);
const empty = page.locator(`li[data-game-id="${boards[3].game_id}"]`);
await empty.focus();
await page.keyboard.press("1");
await page.waitForFunction((id) => !document.querySelector(`li[data-game-id="${id}"]`), boards[3].game_id, { timeout: 8000 });
await page.getByRole("tab", { name: /Confirmed/ }).click();
await page.waitForFunction((id) => document.querySelector(`li[data-game-id="${id}"]`)?.innerText.includes("1:0"), boards[3].game_id, { timeout: 8000 });
check("keyboard sets a result", true);
await page.getByRole("tab", { name: /Attention/ }).click();
await page.waitForFunction(() => document.body.innerText.includes("Nothing needs you"), null, { timeout: 8000 });
check("attention filter empties out", true);
check("footer offers release", await page.getByRole("button", { name: "Release round 3" }).isVisible());

// The search input must swallow the shortcut keys.
await page.getByRole("tab", { name: /All/ }).click();
await page.getByLabel("search boards").fill("1");
await page.waitForFunction(() => document.querySelectorAll("li[data-game-id]").length === 1, null, { timeout: 5000 });
check("search by board number narrows to one", true);
await page.getByLabel("search boards").fill("mueller");
await page.waitForFunction(() => document.querySelectorAll("li[data-game-id]").length === 1, null, { timeout: 5000 });
check("search by name narrows to one", true);
await page.getByLabel("search boards").fill("");
await page.getByRole("tab", { name: /Attention/ }).click();

// 5. Release, then export; the download lands and the hand-off shows.
await page.getByRole("button", { name: "Release round 3" }).click();
await page.getByRole("dialog").getByRole("button", { name: "Release", exact: true }).click();
await page.waitForFunction(() => document.body.innerText.includes("released"), null, { timeout: 8000 });
await page.waitForSelector("text=released — ready to export");
check("release changes the round state", true);
await page.getByRole("button", { name: /Export for Swiss-Manager/ }).click();
const [download] = await Promise.all([
  page.waitForEvent("download"),
  page.getByRole("dialog").getByRole("button", { name: "Export and freeze" }).click(),
]);
check("export downloads the pairing file", download.suggestedFilename() === "A-round3.txt", download.suggestedFilename());
await page.waitForFunction(() => document.body.innerText.includes("Now in Swiss-Manager"), null, { timeout: 8000 });
check("hand-off names the manager's menu", await page.getByText(/Daten Import\/Export/).isVisible());
await page.screenshot({ path: path.join(SHOTS, "handoff.png"), fullPage: true });
const [again] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download again" }).click()]);
check("download again yields the same file", again.suggestedFilename() === "A-round3.txt");
check("no more result buttons on a frozen round", (await page.getByRole("group", { name: "set result" }).count()) === 0);

// 6. Import round 4 from the hand-off link; the home shows the loop advanced.
await page.getByRole("link", { name: "Import round 4" }).click();
await page.waitForURL(/\/import\?section=A/);
check("section prefilled and manager locked", (await page.getByLabel("Section").inputValue()) === "A" && (await page.getByLabel("Tournament manager").isDisabled()));
await page.setInputFiles('input[type="file"]', { name: "FIDE_Export_r4.TXT", mimeType: "text/plain", buffer: Buffer.from(readFileSync(FIX + "round4_paired.trf")) });
await page.getByRole("button", { name: "Preview the changes" }).click();
await page.waitForSelector("text=What round 4 changes");
const mustRead = await page.getByText("Read before importing").isVisible();
if (mustRead) await page.getByLabel("I have read the changes above.").check();
await page.getByRole("button", { name: /Import round 4/ }).click();
await page.waitForURL(/\/rounds\//);
await page.waitForSelector("text=Section A · Round 4");
check("round 4 is open on its board", true);
await page.goto(BASE + `/admin/t/${tournamentId}`, { waitUntil: "networkidle" });
await page.waitForSelector("text=Earlier:");
check("home shows round 4 with earlier rounds", await page.getByRole("link", { name: "Round 4" }).isVisible());
await page.screenshot({ path: path.join(SHOTS, "home.png"), fullPage: true });

// 7. Devices: issue in the UI, open the poster, revoke.
await page.getByRole("link", { name: "Devices" }).click();
await page.getByPlaceholder(/poster/).fill("wall by the door");
await page.getByRole("button", { name: "Issue a QR code" }).click();
await page.waitForSelector('dialog[open] svg[role="img"]');
check("issue renders a QR", true);
await page.getByRole("button", { name: "Open as a poster" }).click();
await page.waitForURL(/\/poster/);
await page.waitForSelector("text=Scan to enter your result");
check("poster shows the code", (await page.locator('svg[role="img"]').count()) === 1);
await page.screenshot({ path: path.join(SHOTS, "poster.png"), fullPage: true });
await page.goBack();
await page.waitForSelector("text=wall by the door");
const row = page.locator("li", { hasText: "wall by the door" });
await row.getByRole("button", { name: "Revoke" }).click();
await page.getByRole("dialog").getByRole("button", { name: "Revoke" }).click();
await page.waitForFunction(() => document.body.innerText.includes("revoked"), null, { timeout: 8000 });
check("revoke shows on the list", true);

// 8. Phone widths render without horizontal overflow.
for (const width of [375, 768]) {
  const small = await browser.newContext({ viewport: { width, height: 800 } });
  await small.addInitScript((tok) => localStorage.setItem("seebach.staff-token", tok), TOKEN);
  const p = await small.newPage();
  for (const path of [`/t/${tournamentId}`, `/t/${tournamentId}/rounds/${roundId}`, `/t/${tournamentId}/import`, `/t/${tournamentId}/devices`]) {
    await p.goto(BASE + "/admin" + path, { waitUntil: "networkidle" });
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    check(`no horizontal overflow at ${width}: ${path.split("/").slice(3).join("/") || "home"}`, !overflow);
  }
  await small.close();
}

await browser.close();
console.log(failures.length ? `\n${failures.length} FAILED` : "\nthe arbiter's round works end to end through the admin UI");
process.exit(failures.length ? 1 : 0);
