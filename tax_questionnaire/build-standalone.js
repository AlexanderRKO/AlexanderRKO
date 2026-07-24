#!/usr/bin/env node
/*
 * build-standalone.js — bundle the questionnaire into single, portable HTML files.
 * --------------------------------------------------------------------------------
 * The form is already plain HTML/CSS/JS. This script inlines the linked stylesheet
 * and scripts so the whole tool becomes ONE .html file with no separate assets —
 * host it anywhere static, email it, or open it straight off disk.
 *
 * Usage:  node build-standalone.js
 * Output: standalone/lms-new-client-questionnaire.html   (client form)
 *         standalone/lms-questionnaire-results.html       (staff results view)
 *
 * No dependencies. Re-run after editing schema.js / styles.css / etc.
 */

const fs = require("fs");
const path = require("path");

const ROOT = __dirname;
const DIST = path.join(ROOT, "standalone");

function read(file) {
  return fs.readFileSync(path.join(ROOT, file), "utf8");
}

// Inline <link rel="stylesheet" href="x.css"> and <script src="x.js"></script>
// for *local* files only (leave absolute URLs, e.g. a CDN, untouched).
function inline(html) {
  // Stylesheets
  html = html.replace(
    /[ \t]*<link[^>]*rel=["']stylesheet["'][^>]*href=["']([^"':]+\.css)["'][^>]*>\s*/gi,
    (m, href) => `  <style>\n${read(href)}\n  </style>\n`
  );
  // Scripts with a local src
  html = html.replace(
    /[ \t]*<script[^>]*src=["']([^"':]+\.js)["'][^>]*>\s*<\/script>\s*/gi,
    (m, src) => {
      // Guard against any literal </script> inside the JS breaking the tag.
      const js = read(src).replace(/<\/script>/gi, "<\\/script>");
      return `  <script>\n${js}\n  </script>\n`;
    }
  );
  return html;
}

function build(inputHtml, outputName) {
  const bundled = inline(read(inputHtml));
  const outPath = path.join(DIST, outputName);
  fs.writeFileSync(outPath, bundled);
  const kb = (Buffer.byteLength(bundled) / 1024).toFixed(0);
  // Sanity check: no local asset references should remain.
  const leftover = bundled.match(/(?:href|src)=["'][^"']+\.(?:css|js)["']/gi) || [];
  const localLeft = leftover.filter((s) => !/https?:/i.test(s));
  console.log(`✓ ${outputName}  (${kb} KB)` + (localLeft.length ? `  ⚠ unresolved: ${localLeft.join(", ")}` : ""));
}

fs.mkdirSync(DIST, { recursive: true });
build("index.html", "lms-new-client-questionnaire.html");
build("results.html", "lms-questionnaire-results.html");
console.log("\nStandalone files written to standalone/. Each is a single, self-contained HTML file.");
