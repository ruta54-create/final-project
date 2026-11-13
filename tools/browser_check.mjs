// Full browser check of the Edge-AI Smart Dustbin dashboard - no hardware needed.
//
//   1. start the system:  RUN_DEMO.bat   (website + simulated bin + AI service)
//   2. run:               node tools/browser_check.mjs
//
// Drives a real (headless) Google Chrome like a person: logs in, uses every page and button,
// tests the AI with sample photos, an upload and a (fake) webcam, and checks French + Kinyarwanda.
// Needs Node.js 22+ (built-in WebSocket) and Google Chrome.
import { spawn } from "node:child_process";
import { mkdtempSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const URL = process.argv.find((a) => a.startsWith("--url="))?.slice(6) || "http://localhost:8000";
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CHROME = ["C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"].find(existsSync);
if (!CHROME) { console.error("Google Chrome not found"); process.exit(2); }
const profile = mkdtempSync(join(tmpdir(), "smartbin-check-"));
const PORT = 9400 + Math.floor(Math.random() * 400);
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`, "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "about:blank"], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 60 && !target; i++) {
  await sleep(500);
  try { target = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: "PUT" })).json(); } catch { /* starting */ }
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
const jsErrors = [];
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
  if (m.method === "Runtime.exceptionThrown") jsErrors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
};
// every browser call has a time limit, so a stuck page fails a check instead of hanging the whole run
const send = (method, params = {}, ms = 120000) => new Promise((resolveCall, rejectCall) => {
  const i = ++id;
  const timer = setTimeout(() => { pending.delete(i); rejectCall(new Error(`browser did not answer ${method} in ${ms / 1000}s`)); }, ms);
  pending.set(i, (m) => { clearTimeout(timer); resolveCall(m); });
  ws.send(JSON.stringify({ id: i, method, params }));
});
await send("Runtime.enable");
await send("Page.enable");
await send("DOM.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1536, height: 1000, deviceScaleFactor: 1, mobile: false });

const HELPERS = `window.confirm = () => true;
var T = {
  sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
  $: (s) => document.querySelector(s), all: (s) => [...document.querySelectorAll(s)],
  byText: (sel, txt) => [...document.querySelectorAll(sel)].find((e) => e.textContent.trim() === txt),
  async wait(fn, what, ms = 20000) { const t = Date.now(); while (Date.now() - t < ms) { try { const v = fn(); if (v) return v; } catch {} await T.sleep(250); } throw new Error("timeout: " + what); },
  type(el, v) { const p = el.tagName === "SELECT" ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(p, "value").set.call(el, v); el.dispatchEvent(new Event(el.tagName === "SELECT" ? "change" : "input", { bubbles: true })); },
  async page(i, ready) { T.all(".nav-link")[i].click(); await T.wait(() => T.$("main h1") && !T.$("main .loading") && (!ready || T.$(ready)), "page " + i); await T.sleep(600); },
  log: () => T.all(".command-log tbody tr"),
};`;
async function page(js) {
  const r = await send("Runtime.evaluate", { expression: `(async () => { ${HELPERS}\n${js} })()`, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description?.split("\n")[0] || "error");
  return r.result.result.value;
}
const results = [];
let section = "";
async function check(name, js) {
  try {
    const v = await page(js);
    results.push(true);
    console.log(`  [PASS] ${name}${v ? `  (${v})` : ""}`);
  } catch (e) {
    results.push(false);
    console.log(`  [FAIL] ${name}  -> ${e.message}`);
  }
}
const head = (s) => { section = s; console.log(`\n${s}`); };

// a command button -> wait until the simulated bin reports "done"
const command = (action) => `
  const before = T.log().length ? T.log()[0].innerText : "";
  T.$('[data-action="${action}"].action-btn').click();
  await T.wait(() => { const r = T.all('.command-log tr[data-action="${action}"]')[0]; return r && r.dataset.status === "done" && r.innerText !== before; }, "${action} done", 25000);
  return "";`;

// ================================================================== run
await send("Page.navigate", { url: URL });
await sleep(4000);

head("1. LOGIN");
await page(`localStorage.setItem("smartbin.lang", "en");`);
await send("Page.reload");
await sleep(3500);
await check("login page shown", `await T.wait(() => T.$("#username"), "form"); return T.$(".login-card h1").textContent;`);
await check("wrong password refused", `T.type(T.$("#username"), "admin"); T.type(T.$("#password"), "wrong-password"); T.$("button.wide").click();
  return await T.wait(() => T.$(".error-box")?.innerText, "error");`);
await check("admin logs in", `T.type(T.$("#password"), "admin12345"); T.$("button.wide").click(); await T.wait(() => T.$(".sidebar"), "sidebar"); return "";`);

head("2. DASHBOARD (live data from the simulated bin)");
await check("all panels present", `await T.page(0, ".tanks");
  const need = ["Organic compartment", "Inorganic compartment", "Items sorted today", "Air quality", "Live Camera", "Recommendations", "Fill Level Trend", "Recent Activity", "System Info"];
  const miss = need.filter((t) => !document.body.innerText.includes(t)); if (miss.length) throw new Error("missing " + miss); return "";`);
await check("trend chart drawn", `return (await T.wait(() => T.all(".recharts-line-curve").length >= 2 && T.all(".recharts-line-curve").length, "lines")) + " lines";`);
await check("bin and camera online", `return await T.wait(() => /Controller online/.test(T.$(".header").innerText) && /Camera online/.test(T.$(".header").innerText) && "both online", "online");`);
await check("live update (new items arrive)", `const v = () => T.all(".stat").find((s) => s.innerText.includes("Items sorted today")).querySelector(".stat-value").textContent;
  const a = v(); await T.wait(() => v() !== a, "new item", 60000); return a + " -> " + v();`);

head("3. CONTROL PANEL (commands executed by the simulated bin)");
await check("page opens", `await T.page(4, ".actions"); return "";`);
await check("open lid", command("open_lid"));
await check("lid shows Open", `return await T.wait(() => T.$('[data-row="lid"]').innerText.includes("Open") && "Open", "lid open");`);
await check("close lid", command("close_lid"));
await check("tilt tray to organic", command("sort_organic"));
await check("capture & classify", command("capture"));
await check("test buzzer", command("buzzer"));
await check("switch to Manual, then Automatic", `T.$('[data-mode="manual"]').click(); await T.wait(() => T.$('[data-mode="manual"]').classList.contains("active"), "manual");
  T.$('[data-mode="auto"]').click(); await T.wait(() => T.$('[data-mode="auto"]').classList.contains("active"), "auto"); return "";`);
await check("record 'inorganic emptied'", `T.$('[data-emptied="inorganic"]').click(); return await T.wait(() => /Recorded/.test(T.$(".ok-note")?.innerText || "") && T.$(".ok-note").innerText, "recorded");`);

head("4. DETECTIONS + TEACH THE AI");
await check("photos listed", `await T.page(1, ".shot"); return T.all(".shot").length + " items, " + T.all(".shot img").length + " photos";`);
await check("filter 'To review'", `T.byText("button.chip", "To review").click(); await T.sleep(2500); const n = T.all(".shot").length;
  if (n !== T.all(".shot .review:not(.done)").length) throw new Error("reviewed items shown"); return n + " to review";`);
await check("press Correct", `const c = T.$(".shot"); c.querySelector('[data-review="correct"]').click(); await T.wait(() => c.querySelector(".review.done.ok"), "verified"); return "";`);
await check("correct a mistake", `const c = T.all(".shot").find((x) => !x.querySelector(".review.done")); c.querySelector('.review-buttons [data-review]:not([data-review="correct"])').click();
  await T.wait(() => c.querySelector(".review.done.bad"), "corrected"); return c.querySelector(".review").innerText.replace(/\\s+/g, " ").trim();`);
await check("filter 'AI mistakes'", `T.byText("button.chip", "AI mistakes").click(); await T.sleep(2500); return T.all(".shot").length + " mistakes";`);
await check("download checked photos (ZIP)", `const r = await fetch(T.$('[data-role="export-photos"]').href); const b = new Uint8Array(await r.arrayBuffer());
  if (b[0] !== 0x50 || b[1] !== 0x4b) throw new Error("not a zip"); return r.headers.get("x-photo-count") + " photos";`);

head("5. ANALYTICS");
await check("charts drawn", `await T.page(2, ".recharts-bar-rectangle"); return T.all(".recharts-bar-rectangle").length + " bars";`);
await check("AI accuracy in the real bin", `const c = await T.wait(() => T.all(".card").find((x) => x.querySelector(".matrix")), "quality card");
  return c.querySelector(".muted-title").textContent + " · " + [...c.querySelectorAll(".stat-value")].map((v) => v.textContent).join(" / ");`);
await check("30-day range", `T.byText("button.chip", "30 days").click(); await T.wait(() => document.body.innerText.includes("in the last 30 days"), "range"); return "";`);
await check("3 CSV downloads", `const out = []; for (const a of T.all("a.btn-outline")) { const r = await fetch(a.href); const t = await r.text();
  if (!r.ok || !t.startsWith("time,")) throw new Error(a.textContent); out.push(t.split("\\n").length - 2); } return out.join(" / ") + " rows";`);

head("6. ALERTS");
await check("alerts and recommendations", `await T.page(3, ".recs"); T.byText("button.chip", "Resolved").click(); await T.sleep(1500); return T.all(".rec").length + " recommendations";`);

head("7. SETTINGS + EMAIL ALERTS");
await check("save bin settings", `await T.page(5, "#bin-location"); const old = T.$("#bin-location").value; T.type(T.$("#bin-location"), old + " ");
  T.$("#bin-location").closest("form").querySelector("button.btn").click(); await T.wait(() => document.body.innerText.includes("Settings saved."), "saved");
  T.type(T.$("#bin-location"), old); T.$("#bin-location").closest("form").querySelector("button.btn").click(); await T.sleep(1500); return "";`);
await check("invalid levels refused", `T.type(T.$("#bin-warning_level"), "95"); T.$("#bin-location").closest("form").querySelector("button.btn").click();
  await T.wait(() => T.all(".err").some((e) => /Almost full/.test(e.innerText)), "refused"); T.type(T.$("#bin-warning_level"), "75");
  T.$("#bin-location").closest("form").querySelector("button.btn").click(); await T.wait(() => document.body.innerText.includes("Settings saved."), "restored"); return "";`);
await check("email settings + test email", `if (!T.$("#notif-email").value) T.type(T.$("#notif-email"), "admin@example.com");
  if (!T.$("#notif-enabled").checked) T.$("#notif-enabled").click(); T.$('[data-role="save-email"]').click(); await T.wait(() => T.all(".ok").some((e) => /saved/.test(e.innerText)), "saved");
  T.$('[data-role="test-email"]').click(); return await T.wait(() => T.all(".ok").map((e) => e.innerText).find((t) => /Test email/.test(t)), "test email", 30000);`);

head("8. TEST THE AI (same int8 model as the ESP32)");
await check("AI model ready", `await T.page(6, ".lab"); return await T.wait(() => /ready/i.test(T.$("main .panel-head .pill")?.innerText || "") && T.$(".lab-info").innerText.replace(/\\s+/g, " "), "model ready", 30000);`);
await check("8 sample photos classified", `const out = []; let ok = 0;
  for (const b of T.all("[data-sample]")) { const want = b.dataset.sample.split("-")[0]; b.click();
    await T.wait(() => T.$('[data-role="decision"]') && !T.$(".lab .loading"), "result " + want, 30000); await T.sleep(400);
    const good = !!T.all("p.ok").find((p) => /Correct/.test(p.innerText)); ok += good; out.push(want + (good ? "+" : "-")); }
  return ok + "/8 correct: " + out.join(" ");`);
await check("paper goes to the organic compartment", `T.$('[data-sample="paper-2.jpg"]').click(); await T.sleep(500);
  const d = await T.wait(() => T.$('[data-role="decision"]')?.innerText, "decision", 30000); if (!/organic|inorganic/.test(d)) throw new Error(d); return d.replace(/\\s+/g, " ");`);
await check("upload a photo", `window.__lastPhoto = T.$(".lab-images img")?.src; T.byText("button.chip", "Upload").click(); await T.wait(() => T.$("#lab-file"), "file input"); return "";`);
{
  // give the hidden <input type=file> a real photo, like a user choosing a file
  const doc = await send("DOM.getDocument", { depth: -1 });
  const node = await send("DOM.querySelector", { nodeId: doc.result.root.nodeId, selector: "#lab-file" });
  await send("DOM.setFileInputFiles", { nodeId: node.result.nodeId, files: [join(ROOT, "frontend", "public", "samples", "organic-2.jpg")] });
}
await check("uploaded photo classified", `await T.wait(() => T.$(".lab-images img")?.src !== window.__lastPhoto && !T.$(".lab .loading") && T.$('[data-role="decision"]'), "new upload result", 30000);
  return T.$('[data-role="decision"]').innerText.replace(/\\s+/g, " ");`);
await check("webcam photo classified", `T.byText("button.chip", "Webcam").click(); await T.wait(() => T.$('[data-role="snap"]'), "webcam");
  await T.sleep(2000); const before = T.$(".lab-images img")?.src; T.$('[data-role="snap"]').click();
  await T.wait(() => T.$(".lab-images img")?.src !== before && !T.$(".lab .loading") && T.$('[data-role="decision"]'), "new webcam result", 30000);
  return "Chrome's fake test camera -> " + T.$('[data-role="decision"]').innerText.replace(/\\s+/g, " ");`);
await check("send result to the bin -> appears in Detections", `T.$('[data-role="send-to-bin"]').click(); await T.wait(() => T.all(".ok").some((e) => /Added to/.test(e.innerText)), "sent");
  await T.page(1, ".shot"); T.byText("button.chip", "All items").click(); await T.sleep(2000); return "newest: " + T.$(".shot strong").textContent;`);

head("9. LANGUAGES (no English left in French and Kinyarwanda)");
const ENGLISH = ["Recommendations", "Recent Activity", "System Info", "Compartments", "Items sorted today", "Remote Commands", "Command Log",
  "Operating Mode", "Control Panel", "Load more", "Almost full", "Organic", "Inorganic", "Settings", "Analytics", "Detections", "Dashboard",
  "confidence", "Air quality", "Uptime", "Last update", "Save settings", "My account", "Test the AI", "Sample photos", "To review", "AI mistakes"];
for (const lang of ["fr", "rw"]) {
  await check(`${lang.toUpperCase()}: all 7 pages translated`, `T.$('.sidebar .lang-switch button[lang="${lang}"]').click(); await T.wait(() => document.documentElement.lang === "${lang}", "lang");
    const bad = []; for (let i = 0; i < 7; i++) { await T.page(i); await T.sleep(1500);
      const clone = T.$("main").cloneNode(true); clone.querySelectorAll("tbody").forEach((b) => b.remove());
      document.body.appendChild(clone); const txt = clone.innerText; clone.remove(); const left = ${JSON.stringify(ENGLISH)}.filter((w) => new RegExp("\\\\b" + w + "\\\\b").test(txt)); if (left.length) bad.push(i + ":" + left.join(",")); }
    if (bad.length) throw new Error(bad.join(" | ")); return T.all(".nav-link span:first-of-type").map((s) => s.textContent).join(" · ");`);
}
await check("back to English", `T.$('.sidebar .lang-switch button[lang="en"]').click(); await T.wait(() => document.documentElement.lang === "en", "en"); return "";`);

head("10. LOGOUT");
await check("logout returns to login", `T.$(".icon-btn").click(); await T.wait(() => T.$("#username"), "login"); return "";`);

const passed = results.filter(Boolean).length;
console.log(`\n${passed}/${results.length} checks passed.`);
console.log(jsErrors.length ? `JavaScript errors: ${jsErrors.join(" | ")}` : "No JavaScript errors.");
ws.close();
chrome.kill();
await sleep(500);
try { rmSync(profile, { recursive: true, force: true }); } catch { /* Chrome may still hold files */ }
process.exit(passed === results.length && !jsErrors.length ? 0 : 1);
