# Port check: each app screen against its plate

Screenshots: `demo/app-screens/<screen>.png`, full page at 1440 px wide, headless Chrome, from the Vite dev server (`127.0.0.1:5173`) with the local API (`127.0.0.1:8765`, FalkorDB on 6380) behind the dev proxy. Results is the whole app page, which runs past plate 01; compare its first 2,500 px with the plate. The fixed paper grain and sheet frame cover only the first 1,000 px of a full-page capture, so they stop partway down each image. That is a capture effect, not a layout fault.

Round 3 (this file): the plate head, the stat cells, the ruled rows, the blank tiles and the next-plate foot are now shared components in `ui/src/data.tsx`, built from the same tokens as the plates. The sheet frame carries the plates' ruler ticks. The title block ends in a `Built` row with the commit the page was built from.

Comparison rule: the plate body is compared. The app keeps its own header (pack line and screen navigation) in place of the plate navigator (prev, next, index), because the app navigates between screens, not plates.

## Per screen

- results.png: **matches plate 01.** Kicker, headline with serif turn (the numbers come from the file), lede, title block, the three stat cells, the ten-cell quarter row on one line (five checks as marks, Pressure window count and dots, Held stamp, last quarter selected), the lane chart with the lone-keeper condition, the four NOT COMPUTED tiles, and the table with cadence, active keepers, usual path, unread and decision. Not done: count-up figures and draw-on chart animation (`port_inventory.md`). The detail, evidence, takeover, who-saw, trust and hardening sections continue below the plate as before.
- packager.png: **does not match plate 07**, for one reason. The plate's question reads "Before the Debian package maintainer decided, could that role see…". The app's question also names the place and the decision time (`Before Debian package maintainer decided at debian-bts on 2024-03-25T20:28:05Z, …`), because `questionFor` and its test fix that wording. Everything else matches: head, choice row, large serif question, gap figure with its caption, gap table, lower-bound note, next-plate foot.
- inbox.png: **does not match plate 12.** Head, ruled rows (number, quarter, Held mark, headline, arrow), provenance line and foot match. Two differences: the plate has the "xz · public record / tallowdate · synthetic" switch, and the local API serves the xz notes only; and each row carries a "Show me why" link before the arrow, which the plate does not draw.
- playbook.png: **does not match plate 14.** The two figures and the five step rows (dismissed, proposed, safety rules, regression gate, end state) are read from `learning_verify.json` and match the plate. The Approve row matches. The app adds a block for the live learned exceptions from `/api/inbox/playbook` (empty now: "No learned exceptions yet"), which the plate does not have.
- connect.png: **matches plate 15.** The empty state now shows the saved run in `connect_repo_run.json`: figures, steps, metric table, and the hatched takeover-cost tile. Controls are live where the plate shows a disabled preview: the repository is an editable field (underlined) and Connect runs the local API. After a live run the screen shows that run's own result, with its summary lines and the takeover and guardians reasons.
- census.png: no plate. Behaviour kept, restyled with tokens.

## Not done in this round

- Count-up figures, draw-on charts, and the message-square reveal (see `port_inventory.md`).
- Plate head on Census (no plate), and on the Inbox note and "Show me why" pages (plate 13 is not ported).
