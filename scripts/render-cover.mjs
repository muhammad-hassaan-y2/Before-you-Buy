// Renders submission/cover.svg to submission/cover.png at the 16:9 size the form wants.
// Playwright resolves from frontend/, because that is where the browser is installed.
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "frontend", "package.json"));
const { chromium } = require("@playwright/test");

const width = Number(process.argv[2] ?? 1920);
const source = path.join(root, "submission", "cover.svg");
const target = path.join(root, "submission", "cover.png");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height: (width * 9) / 16 } });
await page.goto(pathToFileURL(source).href);
await page.waitForTimeout(500);
await page.screenshot({ path: target });
await browser.close();
console.log(`${target} at ${width}x${(width * 9) / 16}`);
