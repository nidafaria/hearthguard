# Labelling the 60 held-out messages

File to fill in: `eval/labels/to_label.csv`. It has 60 rows and three columns: `id`, `text_first_600`, `label`.
Only the `label` column is yours. Do not change `id` or the text.

## What to do

1. Open `to_label.csv` in a spreadsheet or a text editor. Save it as CSV (UTF-8) with the same name.
2. Read the text of each row. For each one, ask: does the AUTHOR say something of this kind in their own words?
3. Write the label (or labels) in the `label` column.
4. Run `uv run python eval/labels/check_labels.py` to count what is filled and see anything wrong.

## Allowed labels

Write one or more of these words exactly. To give several, put a semicolon between them, like `PRESSURE;URGENCY`.

| Label | Use it when the author... |
|---|---|
| `NONE` | says nothing of any kind below. Most messages are this. |
| `PRESSURE` | pushes the maintainer to act faster or differently, or complains they are too slow |
| `URGENCY` | stresses time pressure or a deadline |
| `VOUCH` | says a person is trustworthy or good, or recommends them for a role |
| `REQUESTS_PRIVILEGE` | asks to be given rights over the project (commit, release, maintainer) |
| `CAPACITY_STATEMENT` | says someone's time, resources or ability to maintain is limited |
| `CHANGE_REQUEST` | asks that who maintains or controls the project change. A plain "please review my patch" is NOT this |
| `HANDOVER_ANNOUNCEMENT` | says responsibility or access has been, or is being, handed over |

`NONE` must be alone. Lines like `[person]`, `[email]`, `[url]` are removed names and links.

## Two things to know

- The text is cut at 600 characters to make reading quick. If a message is longer, the claim might be in the part you cannot see. The full text is in `eval/results/reader_labelsheet.csv` (column `cleaned_text`). If in doubt, check it there.
- This file is a simple sheet. The scorer (`eval/reader_score.py`) reads the older sheet `eval/results/reader_labelsheet.csv`, which needs `yes` or `no` for each of the seven kinds. Your answers here do not feed the scorer by themselves; someone must copy them across. This file does not change that sheet.

Nothing in this folder is filled in by the AI. Do not ask the Reader (or any model) to label for you; that would make the score meaningless.
