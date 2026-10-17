# Port check: each app screen against its plate

Screenshots: `demo/app-screens/<screen>.png`, taken with headless Chrome at 1440 × 1000 from the Vite dev server (`127.0.0.1:5173`). The inbox, playbook, and census screens use the local API (`127.0.0.1:8765`) through the dev proxy.

Result: 6 app screens ported to the tokens, fonts, and components. 0 of the 5 screens with a plate match it. 1 screen (Census) has no plate. Every screen's gap is listed below.

Fixed in this port (small): the default theme is Paper, as in the demo; a Paper/Night switch is in the header; the Packager question is serif italic; neutral banners use the cell colour, not the synthetic tint.

Not fixed (large, left for a follow-up): the layout changes listed per screen below. The count-up, word-rise, and draw-on motions are not ported (see `port_inventory.md`).

## Per screen

- results.png: does not match plate 01, because the replay is a table, not the quarter strip, the timeline is a separate chart further down, the plate head (title block, lede in a cell) is missing, and the headline does not split into rising words.
- connect.png: does not match plate 15, because the plate's headline row, title block, and metric table are missing; the app shows only the form, and the Connect button is square as in the design.
- packager.png: does not match plate 07, because the demo's decision cards and large question block are a choice grid, and the app uses a dropdown; the question itself is now serif italic as in the design.
- inbox.png: does not match plate 12, because the demo's ruled list rows with large headlines are a plain table in the app, the row links are underlined, and the screen has no header nav (the inbox route does not render `Header`).
- playbook.png: does not match plate 14, because the demo's step rows (a three-column grid with big-type titles and a regression counter) are plain text in the app, which has no exceptions yet to show.
- census.png: no plate. Behaviour kept; restyled with tokens. The NOT COMPUTED blank tile's hatching is too faint to see at this screenshot size, so its hatch is not confirmed visually.
