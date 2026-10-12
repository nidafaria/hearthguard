# Blockers, block B

## Row 117: Patience curve (spec 13.7)

- Status: stays PARTIAL.
- Reason: the chart reads `eval/results/ablation_memory.json`, which block C writes (detection rate and lead time against attacker patience, full versus forgetful memory). That file is not on this branch, so the panel shows NOT COMPUTED and names the blocker. No curve is drawn from any other data.
- Command that would produce the input: `make ablation-memory` (still a placeholder in the Makefile, so it exits 1 with "ablation-memory: not built yet").
- Unblock: merge block C's `ablation_memory.json` onto main, then the screen will still need a chart over its schema (`ui/src/Patience.tsx` currently reports presence only).
