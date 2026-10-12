# Reader hand-check: a spot check of 20 items

**This is a spot check of 20 messages. It is not a precision or recall claim.** Twenty messages, of which one holds a clear claim, cannot support a rate.

- **Who judged:** one reviewer (the AI assistant that also wrote the Reader prompt). That is not an independent review. A person on the team should re-check these lines.
- **What was judged:** the cleaned text the Reader saw (quoted lines, emails, URLs and names removed) against the claim definitions in `core/claims/reader.py`. The kinds are PRESSURE, URGENCY, VOUCH, REQUESTS_PRIVILEGE, CAPACITY_STATEMENT, CHANGE_REQUEST (a change to who maintains or controls the project, not a routine patch request) and HANDOVER_ANNOUNCEMENT.
- **Columns:** claims the Reader returned (accepted after validation) | judged correct | judged wrong | judged missing.
- **Counts:** "borderline" means a reasonable reader could go either way; those are not counted as missing.
- **Sample:** `eval/results/reader_sample.json` (every 15th of the 300 in-scope messages, grid anchored at msg00512).

msg00407 | returned 0 | correct 0 | wrong 0 | missing 0 | Build-system suggestion for a Java jar; no claim of a listed kind.
msg00422 | returned 0 | correct 0 | wrong 0 | missing 0 | Benchmark results for a checksum routine; technical only.
msg00437 | returned 0 | correct 0 | wrong 0 | missing 0 | Asks for a CMake compatibility change. A routine change request, not a change of who maintains, so not CHANGE_REQUEST.
msg00452 | returned 0 | correct 0 | wrong 0 | missing 0 | Benchmark code and a correction of a reply-all slip; no claim.
msg00467 | returned 0 | correct 0 | wrong 0 | missing 0 | A question about how a function behaves; no claim.
msg00482 | returned 0 | correct 0 | wrong 0 | missing 0 | One PRESSURE claim was returned and rejected: its quote matched the text word for word but the source has a line break where the model wrote a space (a formatting mismatch, not an invented quote). It was also the wrong label: a technical argument between developers, not pressure on a maintainer. Nothing was missed.
msg00497 | returned 0 | correct 0 | wrong 0 | missing 0 | A maintainer explains a translation-file decision; a policy statement, not a listed kind.
msg00512 | returned 0 | correct 0 | wrong 0 | missing 0 | A patch adding an editor-config file; no request for rights or role.
msg00527 | returned 0 | correct 0 | wrong 0 | missing 0 | A translation submission asking for inclusion in a future release; not a listed kind.
msg00542 | returned 0 | correct 0 | wrong 0 | missing 0 | A patch discussion about a deadlock and a memory limit; offers to write a patch. No claim of a listed kind.
msg00557 | returned 0 | correct 0 | wrong 0 | missing 1 | MISSED PRESSURE: "Patches spend years on this mailing list." and "There is no reason to think anything is coming soon." complain that the project is slow, which is the PRESSURE definition. This is the one clear miss.
msg00572 | returned 0 | correct 0 | wrong 0 | missing 0 | A user asks how to use a Java library correctly; no claim.
msg00587 | returned 0 | correct 0 | wrong 0 | missing 0 | A question about whether build files are in a tarball; no claim.
msg00602 | returned 0 | correct 0 | wrong 0 | missing 0 | A reply thanking a reporter and saying fixes were committed; no claim.
msg00617 | returned 0 | correct 0 | wrong 0 | missing 0 | A technical discussion of a build flag, ending with a request to another person to do it; not a listed kind.
msg00632 | returned 0 | correct 0 | wrong 0 | missing 0 | A release announcement with change notes and an apology for site problems; no claim.
msg00647 | returned 0 | correct 0 | wrong 0 | missing 0 | Benchmark discussion; technical only.
msg00662 | returned 0 | correct 0 | wrong 0 | missing 0 | Code review feedback. Borderline: "There's more than enough pure Java stuff to do for now so any JNI thoughts have to wait" is a mild capacity remark; not counted as missing.
msg00677 | returned 0 | correct 0 | wrong 0 | missing 0 | A contributor on testing plans. Borderline: "I am not sure when I will get opportunity to test out arm64" is about availability for one task; not counted as missing.
msg00692 | returned 0 | correct 0 | wrong 0 | missing 0 | A maintainer accepts a suggestion and commits it; no claim.

**Totals over the 20 messages:** returned 0, judged correct 0, judged wrong 0, judged missing 1 (msg00557), borderline 2 (msg00662, msg00677), rejected by validation 1 (msg00482).

**What this does and does not show.**
- It shows the strict quote check worked: nothing the Reader returned was an invented quote, and the one rejected claim was real text with a line-break difference.
- It shows one clear miss (msg00557) out of one clear claim in this sample. One item is not a rate.
- Most of this sample is routine technical discussion, so zero claims on 19 messages is the expected answer for them. This sample holds almost none of the pressure-era messages, so it says little about recall. A targeted, larger hand-labelled set (`make eval-reader`, spec §10.2) is the real test.
- The prompt was not tuned after seeing these results.
