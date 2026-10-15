# Blocker: Takeover Cost Census (rows 88, 95, 119)

- Built: `ui/src/Census.tsx` and the `#/census` route. The screen is aggregate-only and shows
  NOT COMPUTED with the reason while `eval/results/census.json` is absent.
- Not built: the census ingest (npm structure for N public packages, row 95) and `make census`
  (row 88). No registry records for N packages are cached in `data/raw/`; fetching them is a new
  network ingest, not code over cached data, so it was not done in this pass.
- The schema the screen reads (`n`, `cost_distribution`) is a placeholder defined by the screen;
  the producer must be written to match or the screen updated with it.
- Rows 88, 95 stay NOT STARTED. Row 119 is PARTIAL (screen exists, no data).
