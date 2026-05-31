# ⚡ Showdown Scoreboard

A colourful, animated two-column digital scoreboard. No installation, no build
step — just open the file in any web browser.

## How to use

Open `scoreboard/index.html` in your browser (double-click it, or drag it into
a browser window).

- **Tap the big score button** on either side to add a point to that competitor.
- **Press and hold** a score to **undo** the last point (handy for mis-taps).
- **Click a name** at the top of a column to rename the competitor.
- **– Correct** button fixes an over-count (scores never drop below 0).
- **Points per tap** dropdown lets you score 1, 2, 3, 5 or 10 at a time.
- **👑 crown** automatically appears above whoever is in the lead.
- **🔄 Reset Scores** sets both back to 0 (names are kept).
- Keyboard shortcuts: press **A** to score the left side, **S** for the right.

### Match timer

A **start / pause / reset** clock sits in the header (▶ / ⏸ / ↺). Use it to time
each game or period. It keeps counting across a page refresh, and it pauses
automatically when someone wins.

### Win target & winner banner

The **Play to** dropdown sets a target score (7, 11, 15, 21, 25, or *Off*). When a
competitor reaches it, a celebratory **🏆 Winner** banner pops up with their name
and the final score. From there you can:

- **Rematch** – reset both scores and the timer for a fresh game, or
- **Keep playing** – dismiss the banner and carry on (e.g. to play win-by-two).

Scores, names, points-per-tap, the win target and the timer are all saved
automatically in your browser, so the board survives a page refresh.

## Mobile

The board is fully touch-friendly:

- Columns **stack vertically in portrait** and stay **side-by-side in landscape**.
- A white **flash** and a short **vibration** confirm each tap (no hover needed).
- Layout uses dynamic viewport height (`dvh`) and safe-area insets, so it fits
  correctly around notches and mobile browser toolbars.
- Double-tap-to-zoom and accidental text selection are disabled for clean tapping,
  and buttons use large, thumb-friendly tap targets.

## Install it on your phone (use it like a real app)

The scoreboard is a **PWA** — once you open it once on your phone it installs to
your home screen, runs full-screen with no browser bars, and works **offline**.

### Easiest way: GitHub Pages (a permanent link)

1. On GitHub, go to this repo → **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **Deploy from a branch**.
3. Pick the branch `claude/digital-scoreboard-tggyx` and folder `/ (root)`, then **Save**.
4. Wait ~1 minute, then on your phone open:
   **`https://alexanderrko.github.io/alexanderrko/scoreboard/`**
5. Add it to your home screen:
   - **iPhone (Safari):** Share button → *Add to Home Screen*.
   - **Android (Chrome):** ⋮ menu → *Install app* / *Add to Home Screen*.

Now it launches full-screen like a native app and keeps working with no signal.

### Files that make this work

- `index.html` – the app
- `manifest.json` – name, colours, icons, full-screen mode
- `sw.js` – service worker for offline use
- `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` – home-screen icons
