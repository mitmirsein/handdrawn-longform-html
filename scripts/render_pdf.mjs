#!/usr/bin/env node
/** Convert a static deck HTML file to a 16:9 PDF with local Chrome fonts. */

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright-core";

function usage() {
  console.log("Usage: node scripts/render_pdf.mjs INPUT.html -o OUTPUT.pdf [--chrome PATH]");
}

function parseArgs(argv) {
  const args = { input: null, output: null, chrome: null };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "-h" || token === "--help") return { help: true };
    if (token === "-o" || token === "--output") args.output = argv[++index];
    else if (token === "--chrome") args.chrome = argv[++index];
    else if (!token.startsWith("-") && !args.input) args.input = token;
    else throw new Error(`Unknown argument: ${token}`);
  }
  if (!args.input || !args.output) throw new Error("input and output are required");
  return args;
}

function findChrome(explicit) {
  const candidates = [
    explicit,
    process.env.CHROME_PATH,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome Canary",
  ].filter(Boolean);
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (!found) throw new Error(`Chrome executable not found. Tried: ${candidates.join(", ")}`);
  return found;
}

function portablePath(target, baseDir) {
  const relative = path.relative(baseDir, target);
  return (relative || path.basename(target)).split(path.sep).join("/");
}

function commandOutput(command, args) {
  try {
    return execFileSync(command, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  } catch (error) {
    const details = error?.stderr?.toString?.() || error.message;
    throw new Error(`${command} failed: ${details}`);
  }
}

function pdfPreflight(output, expectedPages, fontsRequired) {
  const info = commandOutput("pdfinfo", [output]);
  const pagesMatch = info.match(/^Pages:\s+(\d+)/m);
  const sizeMatch = info.match(/^Page size:\s+([\d.]+) x ([\d.]+) pts/m);
  if (!pagesMatch || Number(pagesMatch[1]) !== expectedPages) {
    throw new Error(`PDF page count mismatch: expected ${expectedPages}, got ${pagesMatch?.[1] || "unknown"}`);
  }
  if (!sizeMatch || Math.abs(Number(sizeMatch[1]) - 960) > 1 || Math.abs(Number(sizeMatch[2]) - 540) > 1) {
    throw new Error(`PDF page size mismatch: expected 960 x 540 pts, got ${sizeMatch?.[0] || "unknown"}`);
  }
  const fonts = commandOutput("pdffonts", [output]);
  if (fontsRequired) {
    if (!/GangwonEdu(?:All|_OTF)/i.test(fonts)) {
      throw new Error(`PDF does not contain a Gangwon Education font. pdffonts output:\n${fonts}`);
    }
    if (/MalgunGothic|Calibri|ArialMT|TimesNewRoman|NotoSans|AppleSDGothic/i.test(fonts)) {
      throw new Error(`PDF contains an unexpected fallback font. pdffonts output:\n${fonts}`);
    }
  }
  return { info, fonts };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    usage();
    return;
  }
  const input = path.resolve(args.input);
  const output = path.resolve(args.output);
  if (!fs.existsSync(input)) throw new Error(`HTML not found: ${input}`);
  fs.mkdirSync(path.dirname(output), { recursive: true });

  const chrome = findChrome(args.chrome);
  const browser = await chromium.launch({
    headless: true,
    executablePath: chrome,
    args: ["--font-render-hinting=none"],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(input).href, { waitUntil: "load" });
    await page.waitForFunction(() => window.__DECK_READY__ === true, null, { timeout: 30_000 });
    const check = await page.evaluate(() => {
      const pages = [...document.querySelectorAll(".slide-page")];
      const images = [...document.images];
      const fontsRequired = document.documentElement.dataset.fontRequired === "true";
      const overflow = pages.filter((page) => {
        const canvas = page.querySelector(".canvas");
        if (!canvas) return true;
        const rect = canvas.getBoundingClientRect();
        return rect.width > page.clientWidth + 1 || rect.height > page.clientHeight + 1;
      }).length;
      const fonts = fontsRequired ? {
        display: document.fonts.check('700 32px "GangwonEducationModuche"'),
        body: document.fonts.check('300 24px "GangwonEducationModuche"'),
      } : { display: true, body: true };
      return {
        pageCount: pages.length,
        imageCount: images.length,
        brokenImages: images.filter((image) => !image.complete || image.naturalWidth === 0).length,
        overflow,
        layoutIssues: window.__DECK_LAYOUT_ISSUES__ || [],
        fonts,
        fontStatus: document.fonts.status,
      };
    });
    if (!check.pageCount) throw new Error("HTML contains no slide pages");
    if (check.brokenImages) throw new Error(`HTML contains ${check.brokenImages} broken images`);
    if (check.overflow) throw new Error(`HTML contains ${check.overflow} overflowing slide canvases`);
    if (check.layoutIssues.length) {
      throw new Error(`HTML contains ${check.layoutIssues.length} art/text overlap(s): ${JSON.stringify(check.layoutIssues)}`);
    }
    if (check.fontStatus !== "loaded" || !check.fonts.display || !check.fonts.body) {
      throw new Error(`Font preflight failed: ${JSON.stringify(check)}`);
    }

    await page.emulateMedia({ media: "print" });
    await page.pdf({
      path: output,
      width: "1280px",
      height: "720px",
      preferCSSPageSize: false,
      printBackground: true,
      margin: { top: "0in", right: "0in", bottom: "0in", left: "0in" },
      displayHeaderFooter: false,
    });
    const fontsRequired = await page.evaluate(() => document.documentElement.dataset.fontRequired === "true");
    const preflight = pdfPreflight(output, check.pageCount, fontsRequired);
    const manifestBase = path.dirname(output);
    fs.writeFileSync(`${output}.preflight.json`, JSON.stringify({
      input: portablePath(input, manifestBase),
      output: portablePath(output, manifestBase),
      chrome: path.basename(chrome),
      check,
      pdfInfo: preflight.info,
      pdffonts: preflight.fonts,
    }, null, 2));
    console.log(`PDF rendered: ${output}`);
    console.log(`PDF preflight: ${check.pageCount} pages, 960 x 540 pt, fonts=${fontsRequired ? "strict" : "standard"}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(`PDF render failed: ${error.message}`);
  process.exitCode = 1;
});
