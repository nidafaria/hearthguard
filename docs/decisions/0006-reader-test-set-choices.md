# 0006: Reader test-set choices made without the owner

**Status: OPEN.** These were made so work could continue. Each one can be reversed. The Reader prompt stays frozen at version 1 either way.

1. **Shortfall policy: `top-up`.** The year 2023 has 8 in-scope messages (rule needs 15). The test set was built with `top-up`, so it has 60 messages (reader_testset.json records the policy). The alternative, `keep`, would give 53. Changing it means rebuilding the sheet before anyone labels it.
2. **Token cap.** The cost measured on the spot check (1,518.5 tokens per message) projects the 60 test messages at about 91,110 tokens, over the 60,000 cap you set. `make reader-score` therefore refuses to run until you raise `READER_TOKEN_CAP` or lower the reasoning effort (which needs a new frozen version made **before** labels exist).
3. **Haiku labels are not ground truth.** `eval/results/reader_labels_haiku.csv` is an AI second opinion, blind, from Haiku 5.5. Only a person's labels in `reader_labelsheet.csv` count for the score.
4. **The test set was held back from the full run.** `eval.reader_full_run` skips the 60 test-set messages so nobody sees Reader output on them before labelling. As a result the Pressure and Vouch windows have 60 messages the Reader did not read, and the replay shows that.
5. **Messages the Reader cannot read.** A message too long for one request under the account's 8,000 tokens-a-minute limit, or one where the model cannot return valid JSON, is recorded as not read (counted in reader_full_run.json). It is not cut, split, or retried, because that would change what the frozen Reader sees.

## Default chosen for submission, not final (2026-10-18)

- Keep `top-up` (60 messages), keep the 60,000-token cap as set, keep the test set held back, keep unreadable messages recorded as not read. Why: each choice leaves the frozen Reader and the saved results untouched; reversing any of them needs the owner before labels exist.
