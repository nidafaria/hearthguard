# Port inventory: approved design to the app

Source of truth: `demo/index.html` (CSS at lines 8–295, markup 297–311, script 335–858), with `docs/design/system.md` and `docs/design/direction.md`. This file lists what the design defines, and maps every app screen and component to a plate.

## Step 1: what the design defines

### CSS custom properties (`demo/index.html` lines 14–32)

Colour, light (paper, the default):

| Name | Value |
|---|---|
| `--paper` | `#EEEBE4` |
| `--cell` | `#E5E1D8` |
| `--ink` | `#161513` |
| `--graphite` | `#625E57` |
| `--signal` | `#B8340A` |
| `--ultra` | `#2F43C8` |
| `--ultra-tint` | `rgba(47, 67, 200, .06)` |
| `--rule` | `rgba(22, 21, 19, .17)` |
| `--rule-2` | `rgba(22, 21, 19, .32)` |
| `--hatch` | `rgba(22, 21, 19, .22)` |
| `--grain` | `.09` |
| `color-scheme` | `light` |

Colour, dark (night), under `:root[data-theme="dark"]`:

| Name | Value |
|---|---|
| `--paper` | `#121210` |
| `--cell` | `#1B1A17` |
| `--ink` | `#EDE9E0` |
| `--graphite` | `#A19C92` |
| `--signal` | `#FF6A3D` |
| `--ultra` | `#9AA6FF` |
| `--ultra-tint` | `rgba(154, 166, 255, .07)` |
| `--rule` | `rgba(237, 233, 224, .15)` |
| `--rule-2` | `rgba(237, 233, 224, .3)` |
| `--hatch` | `rgba(237, 233, 224, .2)` |
| `--grain` | `.06` |
| `color-scheme` | `dark` |

Non-colour, on `:root`:

| Name | Value |
|---|---|
| `--sans` | `"Geist", "Helvetica Neue", Arial, sans-serif` |
| `--mono` | `"Geist Mono", "Cascadia Mono", Consolas, monospace` |
| `--serif` | `"Instrument Serif", Georgia, serif` |
| `--ease` | `cubic-bezier(.16, 1, .3, 1)` |
| `--pad` | `clamp(16px, 2vw, 28px)` |

### Font families

| Face | Files (in `ui/public/fonts/`, copied from `demo/fonts/`) | Use |
|---|---|---|
| Geist (variable, 100–900) | `geist-var.woff2` | Headlines (weight 640, uppercase, −0.048em), body |
| Geist Mono (variable) | `geist-mono-var.woff2` | Labels, table heads, status marks, sources |
| Instrument Serif 400 | `instrument-serif-400.woff2` | Italic turns in headlines, quotes, the one question per screen |
| Instrument Serif 400 italic | `instrument-serif-400-italic.woff2` | As above |

The demo embeds these as base64. The app loads the same files from `/fonts/` (served by Vite from `ui/public/`), so it works offline. The OFL licence texts are copied beside them.

### Spacing scale

| Token or rule | Value | Used for |
|---|---|---|
| `--pad` | clamp(16px, 2vw, 28px) | Cell padding, table cell side padding |
| Plate head top | clamp(40px, 6vw, 96px) | Top of the page headline (`h1`) |
| Plate head bottom | clamp(24px, 3vw, 40px) | Below the headline |
| Section padding | clamp(28px, 3.4vw, 48px) vertical, `--pad` horizontal | Each cell |
| Frame inset | 8px (4px under 640 px) | The sheet border around the page |

### Corner radius rule

Everything is square. The demo has no `border-radius` anywhere. The port removes every radius from the app (the old stylesheet used 4–8px radii).

### Type scale (rem or clamp, from `docs/design/system.md`)

| Role | Size | Leading | Tracking | Case |
|---|---|---|---|---|
| Plate headline (`h1`) | clamp(2.5rem, 5.6vw, 6rem) | 0.9 | −0.048em | Uppercase, 640 |
| Cell title (`h2`) | clamp(1.5rem, 2.4vw, 2.4rem) | 0.92 | −0.045em | Uppercase, 640 |
| Lede (`.sub`) | clamp(1.05rem, 1.35vw, 1.3rem) | 1.45 | −0.01em | Sentence case |
| Figure (`.gauge-number`) | clamp(3.4rem, 6.6vw, 6.8rem) | 0.82 | −0.06em | 300, tabular |
| Label (table heads, `h3`, card labels) | 10.5–11px mono | 1.2–1.35 | 0.08–0.1em | Uppercase, graphite |
| Body | 15px | 1.5 | — | Sentence case |
| Fine print | 12.5px mono | 1.55 | — | — |
| Question (`.question`) | clamp(1.9rem, 3.8vw, 3.6rem) | 1.04 | −0.012em | Serif italic |

### Components (the design's list, `docs/design/system.md` Components)

| Component | Where it lives in the port |
|---|---|
| Status mark | `.tag` plus a status class, in `style.css`. Set by `Status` in `data.tsx`. FIRED is the only orange filled square; NOT COMPUTED is hatched. |
| Figure | `.gauge-number` in `style.css`, used by `Gauge.tsx` |
| Blank tile | `.blank` plus `p.NOT_COMPUTED`, rendered by `NotComputed` in `data.tsx` (one shared component) |
| Quarter strip | Not ported. The app shows the replay as a table (`ReplayTable` in `App.tsx`). |
| Timeline | `Timeline.tsx` (SVG lanes, ruler-less). Colours from tokens. |
| Evidence trail | `EvidenceCard.tsx` (checklist) |
| Note card | `Thread.tsx` inside `Inbox.tsx`. The question styling is not ported. |
| Gauge | `Gauge.tsx` (cards in a ruled grid) |
| Trust map | `TrustMap.tsx` (Cytoscape). Colours read from tokens at run time. |
| Comparison | Not ported. The app has no before/after cells; `Hardening.tsx` uses a table. |
| Title block | Not ported. The app has no plate title block. |

### Motion (`docs/design/system.md` Motion)

| Motion | Duration, easing | Purpose | Port status |
|---|---|---|---|
| Section entrance (demo `.plate > *` rise) | 600 ms, `--ease` | Cells arrive in reading order | Ported: `section` in `style.css` |
| Figure count-up | 1200 ms, ease-out quart | The headline value | Not ported (needs JS in `Gauge.tsx`; left for a follow-up) |
| Headline words rise from a mask | 900 ms, `--ease`, 40 ms apart | Reading order of the headline | Not ported (the app's `h1` is not split into words) |
| Message squares appear in order | 300 ms each | One square per message | Not ported (no quarter strip) |
| Chart rules and lines draw left to right | 1300 ms, cubic-bezier(.65,0,.35,1) | Time runs left to right | Not ported (SVG draw-on needs `pathLength` work in `Timeline.tsx`, `WhoSaw.tsx`, `Patience.tsx`) |
| Patience arms draw one after another | 700 ms apart, 1300 ms | Compare one memory length at a time | Not ported (see above) |
| Index sheet wipe | 550 ms, `--ease` | Overlay index | No index overlay in the app |
| Facts ticker | 60 s linear | Headline facts | Not ported (the app has no ticker) |
| Reduced motion | all motion off, values at final state | Accessibility | Ported: `@media (prefers-reduced-motion: reduce)` in `style.css` |

Dropped by the design: glows, parallax, custom cursor, hover lifts.

## Step 2: the app

### App screens

Routed screens (`ui/src/App.tsx` `App` and `ui/src/main.tsx` `Root`). These are the "app screens" counted in `port_check.md`:

1. Results (`#/`): `ResultsPage` in `ui/src/App.tsx`
2. Connect your repo (`#/connect`): `ConnectRepo` in `ui/src/ConnectRepo.tsx`
3. Packager question (`#/packager`): `PackagerPage` in `ui/src/App.tsx`
4. Inbox (local) (`#/inbox`): `Inbox` in `ui/src/Inbox.tsx`
5. Playbook (`#/playbook`): `Playbook` in `ui/src/Playbook.tsx`
6. Census (`#/census`): `Census` in `ui/src/Census.tsx`

Components, with the file each one lives in:

| App file | Component | Shown on |
|---|---|---|
| `ui/src/App.tsx` | `Header`, `ThemeSwitch` (new), `ReplayTable`, `QueryBox`, `CheckCard`, `ResultsPage`, `PackagerPage`, `App` | Every routed screen (`Header`); the rest on Results and Packager |
| `ui/src/main.tsx` | `Root` (hash route) | Every screen |
| `ui/src/data.tsx` | `useResult`, `Status`, `NotComputed` (blank tile), `SyntheticTag`, `PublicTag`, `token` (new), `norm`, `computed`, `quarterOf` | Every screen |
| `ui/src/Timeline.tsx` | `Timeline` | Results |
| `ui/src/Gauge.tsx` | `Gauge` | Results (xz and tallowdate) |
| `ui/src/EvidenceCard.tsx` | `EvidenceCard` | Results |
| `ui/src/TwoEndings.tsx` | `TwoEndings` | Results |
| `ui/src/WhoSaw.tsx` | `WhoSaw` | Results |
| `ui/src/TrustMap.tsx` | `TrustMap` | Results |
| `ui/src/Hardening.tsx` | `Hardening` | Results |
| `ui/src/Patience.tsx` | `Patience` | Results |
| `ui/src/Packager.tsx` | `Packager` | Packager |
| `ui/src/ConnectRepo.tsx` | `ConnectRepo`, `MetricRow` | Connect |
| `ui/src/Inbox.tsx` | `Inbox` | Inbox |
| `ui/src/Thread.tsx` | `Thread` | Inbox (per quarter) |
| `ui/src/Playbook.tsx` | `Playbook` | Playbook |
| `ui/src/Census.tsx` | `Census` | Census |
| `ui/src/style.css` | the global stylesheet (replaces the old 62-line sheet) | Every screen |

### Mapping: app file, app screen, matching plate

Plates are the numbered screens of `demo/index.html` (`SCREENS` in the script, lines 770–787).

| App file | App screen | Matching plate |
|---|---|---|
| `ui/src/App.tsx` (`ResultsPage`, `ReplayTable`) | Results: the replay table | 01 The replay |
| `ui/src/Timeline.tsx` | Results: replay timeline chart | 01 The replay |
| `ui/src/App.tsx` (`CheckCard`, `QueryBox`) | Results: detail for a quarter | 02 A quarter, taken apart |
| `ui/src/EvidenceCard.tsx` | Results: evidence card | 03 The evidence trail |
| `ui/src/App.tsx` (grant section) | Results: who was given rights | 04 Who was given rights |
| `ui/src/Gauge.tsx` | Results: takeover cost gauge | 05 Takeover cost |
| `ui/src/WhoSaw.tsx` | Results: who saw what | 06 Who saw what |
| `ui/src/Packager.tsx` (`PackagerPage` route) | Packager question | 07 The packager question |
| `ui/src/TwoEndings.tsx` | Results: two endings | 08 Two timelines |
| `ui/src/TrustMap.tsx` | Results: trust map | 09 The trust map |
| `ui/src/Hardening.tsx` | Results: hardening results | 10 Hardening results |
| `ui/src/Patience.tsx` | Results: patience curve | 11 The patience curve |
| `ui/src/Inbox.tsx` | Inbox (local) | 12 The inbox |
| `ui/src/Thread.tsx` | Note and thread | 13 A note and its why |
| `ui/src/Playbook.tsx` | Playbook | 14 The playbook |
| `ui/src/ConnectRepo.tsx` | Connect your repo | 15 Connect a repository |
| `ui/src/Census.tsx` | Census | no plate |
| `ui/src/App.tsx` (`Header`) | Chrome on every screen | Title block and header, all plates. Plate 00 (overview) has no app screen. |

Routed-screen summary: Results → 01 (its sections also match 02–11); Connect → 15; Packager → 07; Inbox → 12 (with 13 in its thread); Playbook → 14; Census → no plate.

### Hard-coded values found and replaced

- `ui/src/App.tsx`: the default selected quarter was the literal `"2024-Q1"`. It is now the first quarter in `xz_replay.json`, and the reader can still pick any other quarter.
- `ui/src/Patience.tsx`: the three arm colours were hex literals. They are now the tokens `--ink`, `--ultra`, `--signal`.
- `ui/src/TrustMap.tsx`: the node, edge and path colours were hex literals. They now come from the tokens, read at run time by `token()` in `data.tsx`, because Cytoscape cannot use `var()`.
- `ui/src/Timeline.tsx`, `ui/src/WhoSaw.tsx`: SVG colours were set as attributes with `var(...)` (for example `fill="var(--ok)"`). Presentation attributes do not accept `var()`, so those colours never applied. They are now `style` props.
- No number, label, or quote was copied from `demo/index.html`. The demo's embedded JSON is not used anywhere in the app. Every value still comes from `/results/*.json` or the API.
