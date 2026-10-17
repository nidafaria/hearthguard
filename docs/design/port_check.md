# Port check: each app screen against its plate

Screenshots: `demo/app-screens/<screen>.png`, headless Chrome at 1440 × 1000, from the Vite dev server (`127.0.0.1:5173`). The inbox, playbook, and census screens use the local API (`127.0.0.1:8765`) through the dev proxy.

Round 2 (this file): the five screens flagged in round 1 were changed as follows.

- Results: replay table → quarter strip (cells with the seven checks, the Pressure window dots, the decision). Plate head and title block added. Headline rises word by word.
- Connect: plate head and title block added. Metric lists → metric table (shows after a run).
- Packager: dropdown → decision cards in a choice grid. The native select stays, visually hidden, for keyboard and screen-reader use and for the existing tests. Question stays serif italic.
- Inbox: table → ruled list rows. Header nav added. Link underlines removed.
- Playbook: table → one ruled row per step. Shows only when a learned exception exists.

Result: 6 app screens. **0 match their plate fully.** Five have a plate; Census has none. Every gap is listed below.

## Per screen

- results.png: does not match plate 01, because the strip wraps to five cells per row (the plate has ten on one row), the timeline sits below the strip rather than as the plate's main chart, and the strip drops the table's cadence and active-keepers columns, which the plate does not show.
- connect.png: does not match plate 15, because the metric table appears only after a repository run, so the empty state shows the head, title block and form only.
- packager.png: does not match plate 07, because the plate's head and title block were not added to this screen. The decision cards, the serif-italic question and the status marks match the plate.
- inbox.png: does not match plate 12, because the rows use the design's rules and spacing but small body text, not the plate's large headlines, and there is no "Show me why" row action in the list.
- playbook.png: does not match plate 14, because no learned exception is saved in the local data, so the step rows cannot be seen. The step-row markup is in place and is unverified against real data.
- census.png: no plate. Behaviour kept and restyled with tokens. The NOT COMPUTED blank tile's hatching is too faint to confirm at this screenshot size.

## Not done in this round (large)

- Count-up figures, draw-on charts, and the message-square reveal (see `port_inventory.md`).
- The ten-cell quarter row of plate 01.
- Plate head and title block on Packager and Playbook.
