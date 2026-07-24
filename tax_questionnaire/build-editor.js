#!/usr/bin/env node
/*
 * build-editor.js — produce the self-contained in-browser form editor.
 * --------------------------------------------------------------------
 * Embeds the form engine (app.js), styles, page shell (index.html) and the
 * default questions/settings into editor.src.html, producing ONE HTML file your
 * team opens in any browser to edit questions and download a ready-to-use form —
 * no Node, no installs on their side.
 *
 * Run here whenever the engine/styles/schema change:  node build-editor.js
 * Output: standalone/LMS-Form-Editor.html
 */
const fs = require("fs");
const path = require("path");
const ROOT = __dirname;
const read = (f) => fs.readFileSync(path.join(ROOT, f), "utf8");

// JS string literal, with closing tags neutralised so they can't end the
// editor's own <script> block when the browser parses the file.
const jsString = (s) => JSON.stringify(s).replace(/<\//g, "<\\/");

let html = read("editor.src.html");

html = html.split('"@@CSS@@"').join(jsString(read("styles.css")));
html = html.split('"@@APP@@"').join(jsString(read("app.js")));
html = html.split('"@@SHELL@@"').join(jsString(read("index.html")));

// Default questions & settings: inject the real files, then expose them on
// window so the editor can read them regardless of `const` scoping. Neutralise
// any literal </script> (e.g. inside a comment) so it can't end the block early.
const safeJs = (s) => s.replace(/<\/script>/gi, "<\\/script>");
html = html.split("/*@@SCHEMA@@*/").join(safeJs(read("schema.js")) + "\nwindow.FORM_SCHEMA = FORM_SCHEMA;");
html = html.split("/*@@CONFIG@@*/").join(safeJs(read("config.js")) + "\nwindow.FORM_CONFIG = FORM_CONFIG;");

const leftover = html.match(/@@[A-Z]+@@/g);
if (leftover) { console.error("Unresolved tokens:", leftover); process.exit(1); }

fs.mkdirSync(path.join(ROOT, "standalone"), { recursive: true });
const out = path.join(ROOT, "standalone", "LMS-Form-Editor.html");
fs.writeFileSync(out, html);
console.log(`✓ standalone/LMS-Form-Editor.html  (${(Buffer.byteLength(html) / 1024).toFixed(0)} KB)`);
