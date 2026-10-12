# How to label the Reader test set

The sheet is `eval/results/reader_labelsheet.csv`. You are the labeller; the Reader has not been run
on these messages.

**What to label.** For each message, for each of the seven claim kinds, write `yes` or `no`:
does the AUTHOR of the message say something of that kind in their own words, in the
`cleaned_text` column? Every cell must be `yes` or `no`. An empty cell blocks scoring.

**Do not edit `cleaned_text`.** It is exactly what the Reader will be shown, and the scorer refuses
a sheet whose text was changed. Use the `notes` column for doubts. Lines quoted from earlier
messages were already removed, so label only what is left. `[person]`, `[author]`, `[email]` and
`[url]` stand for removed names, addresses and links.

**The seven kinds** (the same wording the Reader was given):

- PRESSURE: pushes the maintainer to act faster or differently, or complains that they are too slow.
- URGENCY: stresses time pressure or a deadline.
- VOUCH: endorses a person as trustworthy or competent, or recommends them for a role.
- REQUESTS_PRIVILEGE: asks to be given rights over the project (commit, release, maintainer role).
- CAPACITY_STATEMENT: says that someone's time, resources or ability to maintain is limited.
- CHANGE_REQUEST: asks that who maintains or controls the project change (add or replace a
  maintainer, someone else should take over). A routine request to review or apply a patch is NOT
  this kind.
- HANDOVER_ANNOUNCEMENT: announces that responsibility or access has been, or is being, handed over.

A message can have none of them, one, or several. Most messages will be all `no`.

**Save the file as CSV (UTF-8)** under the same name. Then run `make.ps1 reader-score`.
