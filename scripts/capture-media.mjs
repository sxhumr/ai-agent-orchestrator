// Drives the GUI with Playwright and writes the README screenshots and demo frames.
// Run it through scripts/capture-media.sh, which seeds the data and starts both servers.
//
//   node scripts/capture-media.mjs <gui-url> <media-dir> <frames-dir>

import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

// Playwright is a devDependency of the frontend, not of the repository root.
const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const [base, mediaDir, framesDir] = process.argv.slice(2);
if (!base || !mediaDir || !framesDir) {
  console.error("usage: capture-media.mjs <gui-url> <media-dir> <frames-dir>");
  process.exit(2);
}
mkdirSync(mediaDir, { recursive: true });
mkdirSync(framesDir, { recursive: true });

const project = `${base}/projects/repair-shop`;
const viewport = { width: 1280, height: 820 };
// Without this, headless Chromium hints Inter into uneven letter spacing.
const browser = await chromium.launch({ args: ["--font-render-hinting=none"] });

async function newPage(theme, deviceScaleFactor) {
  const context = await browser.newContext({ viewport, deviceScaleFactor, reducedMotion: "reduce" });
  await context.addInitScript((t) => localStorage.setItem("forgeflow-theme", t), theme);
  return context.newPage();
}

/** Navigate and wait until the data has loaded and nothing is still animating. */
async function open(page, url, ready) {
  await page.goto(url);
  await page.getByText(ready).first().waitFor();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
}

async function still(page, url, ready, file) {
  await open(page, url, ready);
  await page.screenshot({ path: join(mediaDir, file) });
  console.log(`wrote ${file}`);
}

// Stills, at 2x for sharp README images. These only read data.
const light = await newPage("light", 2);
await still(light, `${project}/requirements`, "Staff manage opening hours", "hero.png");
await still(light, project, "Agent runs", "overview.png");
await still(light, `${project}/requirements/REQ-004`, "History", "requirement.png");
await still(light, `${project}/questions`, "How long is a repair slot", "questions.png");
const dark = await newPage("dark", 2);
await still(dark, `${project}/requirements/REQ-007`, "Related questions", "dark.png");

// Demo: accept a requirement, answer a question, filter. Frames are stitched into a GIF.
const page = await newPage("light", 1);
let frame = 0;
const durations = [];
async function shot(ms) {
  await page.waitForTimeout(350);
  await page.screenshot({ path: join(framesDir, `${String(frame++).padStart(3, "0")}.png`) });
  durations.push(ms);
}

await open(page, `${project}/requirements`, "Reschedule or cancel");
await shot(1600);
await page.getByRole("link", { name: "Reschedule or cancel" }).click();
await page.getByRole("button", { name: "Accept requirement" }).waitFor();
await shot(1400);
await page.getByRole("button", { name: "Accept requirement" }).click();
await page.getByText("accepted as version 2").waitFor();
await shot(2000);

const nav = page.getByRole("navigation", { name: "Project sections" });
await nav.getByRole("link", { name: /Questions/ }).click();
await page.getByText("How long is a repair slot").waitFor();
await shot(1400);
await page.getByRole("button", { name: "Answer this: Q-001" }).click();
const answer = "Forty-five minutes, one bike per slot. Two mechanics, so two bookings at once.";
const field = page.getByLabel("Your answer");
await field.fill(answer);
await field.blur(); // let the onBlur validation settle before saving
await shot(1600);
await page.getByRole("button", { name: "Save answer" }).click();
await page.getByText("Q-001 resolved.").waitFor();
await shot(2000);

await nav.getByRole("link", { name: /Requirements/ }).click();
await page.getByText("Reschedule or cancel").waitFor();
await page.getByRole("button", { name: /^Accepted/ }).click();
await shot(2400);

await browser.close();
console.log(`wrote ${frame} demo frames`);
console.log(JSON.stringify({ durations }));
