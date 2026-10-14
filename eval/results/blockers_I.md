# Block I: open items

No row is left unfinished. Items the lead needs to know:

- Makefile and make.ps1 targets `ablation-memory` and `ablation-algos` are still the placeholder
  (not mine to edit). Until wired, run `uv run python -m eval.ablation_memory` and
  `uv run python -m eval.ablation_algos` with FALKORDB_PORT set. Both need org_tallowdate loaded
  (`make tallowdate-run`).
- Row 99 (FalkorDB MCP wired read-only; Claude Code check_trust demo) and row 26 are not Block I
  rows. The `check_trust` tool they need now exists in mcp_servers/hearthguard-core, but no client
  config or demo script was written.
- Vouch ablation: the frozen Vouch computes its components in plain code, not in a FalkorDB WCC or
  labelPropagation call. The arm removes that component step. The clean set has no VOUCH claims,
  so the file cannot show a false-alarm difference for Vouch. `make false-positives` is the
  measurement for that.
- hearthguard-core `visibility_gaps` reads eval/results/ecosystem_gaps.json (the saved xz run), and
  `why` knows only the xz and tallowdate inbox cases. Neither takes an arbitrary org.
