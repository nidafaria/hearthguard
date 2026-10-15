# Design system: the case drawing

Direction: `docs/design/direction.md`. Voice: `docs/design/copy_guide.md`. Rule: every value on screen is read from a file in `eval/results/`, and the file's name is printed beside it. A self-check (`window.hgCheck()` in the page; `shoot.py` at build review) compares every rendered value with its file.

## Colour

Six hues, each with one job. "Paper" is the primary theme; "Night" mirrors it.

| Token | Job | Paper | Night |
|---|---|---|---|
| `--paper` | Ground, and labels laid over hatching | `#EEEBE4` | `#121210` |
| `--cell` | Emphasis cells, hover | `#E5E1D8` | `#1B1A17` |
| `--ink` | Text, rules, filled cells | `#161513` | `#EDE9E0` |
| `--graphite` | Secondary text, labels, source lines | `#625E57` | `#A19C92` |
| `--signal` | The orange square: a fired move, a headline figure, a gap marker, a worse result | `#B8340A` | `#FF6A3D` |
| `--ultra` | Synthetic data: its tag, its tinted cells, its chart lines | `#2F43C8` | `#9AA6FF` |

`--paper` and `--cell` are one hue at two values. Rules and hatching are `--ink` at 17–32 % opacity. No other colours appear. Public-record data has no tint; synthetic data always carries the ultramarine tag and a 6 % ultramarine cell tint, so a reader can tell them apart at a glance.

### Contrast (WCAG relative luminance, computed)

| Text on | Paper theme | Night theme |
|---|---|---|
| ink on paper | 15.33 | 15.48 |
| ink on cell | 13.98 | 14.36 |
| graphite on paper | 5.41 | 6.86 |
| graphite on cell | 4.94 | 6.37 |
| signal on paper | 4.99 | 6.59 |
| signal on cell | 4.55 | 6.12 |
| ultra on paper | 6.40 | 8.28 |
| ultra on cell | 5.84 | 7.68 |
| paper on ink (filled cells, buttons) | 15.33 | 15.48 |
| paper on signal (button hover) | 4.99 | 6.59 |

Every pair passes WCAG AA for body text (4.5:1).

## Type

All three faces are SIL Open Font License fonts, embedded as WOFF2. Licences are in `demo/fonts/`.

| Role | Face | Use |
|---|---|---|
| Display and text | Geist (variable) | Uppercase headlines at weight 640 and −0.048em tracking; body text |
| Accent | Instrument Serif italic | The turn in a headline, quotes, the question at the end of a note |
| Mono | Geist Mono (variable) | Labels, numbers in tables, file names, queries, title blocks |

Scale (rem):

| Token | Size | Leading | Use |
|---|---|---|---|
| Wordmark | fitted to the full width | 0.78 | Overview only |
| H | clamp(2.5, 5.6vw, 6) | 0.9 | Plate headline |
| Figure XL | clamp(5, 11vw, 11) | 0.82 | The one figure per plate |
| Figure | clamp(3.4, 6.6vw, 6.8) | 0.82 | Figure rows |
| Big-T | clamp(1.5, 2.4vw, 2.4) | 0.92 | Cell titles |
| Lede | clamp(1.05, 1.35vw, 1.3) | 1.45 | Under the headline |
| Body | 0.9375 | 1.5 | Body |
| Fine | 0.78 mono | 1.55 | Notes from files |
| Label | 0.6875 mono caps, 0.08em | 1.35 | Labels, tags, sources |

## Space and shape

Spacing: the cell padding `--pad` is clamp(16px, 2vw, 28px). Vertical rhythm comes from the cells. Plate heads use 40–96 px top padding.

**Corner rule:** everything is square. There are no radii anywhere. A drawing has no rounded corners.

## Motion

All motion is off under `prefers-reduced-motion: reduce`; figures then show their final value.

| Motion | Duration, easing | What it helps the reader understand |
|---|---|---|
| Figure count-up, 0 to the file value | 1200 ms, ease-out quart | Which number is the headline of this plate |
| Headline words rise from a mask, 40 ms apart | 900 ms, cubic-bezier(.16,1,.3,1) | The order in which the sentence reads |
| Message squares appear in reading order | 300 ms each, staggered | Each square is one message, and the count is real |
| Chart rules and lines draw left to right | 1300 ms, cubic-bezier(.65,0,.35,1) | Time runs left to right |
| Patience arms draw one after another, 700 ms apart | 1300 ms | Compare one memory length at a time |
| Index sheet wipes down from the top | 550 ms, cubic-bezier(.16,1,.3,1) | The index is laid over the plate, not a new page |
| Facts ticker scrolls; pauses on hover | 60 s linear | The record's headline facts, in one line |

Dropped: glows, parallax, a custom cursor, hover lifts.

## Components

| Component | One line |
|---|---|
| **Status mark** | A 10 px square plus a mono word. Fired is a filled orange square, Did not fire a ring, Held a bar, NOT COMPUTED a hatched square. |
| **Figure** | One huge light-weight number counted up to its file value, with a caption, a data tag and a `SRC /` line. |
| **Blank tile** | A cell filled with section hatching. NOT COMPUTED, the field name and the file's reason sit on paper labels over the hatching. |
| **Quarter strip** | A row of quarter cells. Each holds five labelled marks, a field of message squares and a rotated HELD stamp. Click one to open it. |
| **Timeline** | SVG lanes for the four moves, then Lone keeper, under a ruler with quarter ticks. |
| **Evidence trail** | A numbered list of the five checks plus the Skeptic, beside the exact archived quotes for that quarter. |
| **Note card** | The note in body type, its question in orange italic serif, and its controls as square buttons. "Show me why" sits beside it as a printed receipt. |
| **Gauge** | A tick-marked dial. When the value is not computed, it is hatched and shows a dash. |
| **Trust map** | Nodes with technical-drawing callouts (A1…P8), keyed to a reference table. |
| **Comparison** | Before → after figures across a row of cells; a worse result turns orange. |
| **Title block** | Every plate's corner: plate, data kind, source files, build commit. |
