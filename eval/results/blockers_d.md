# Block D: blockers

Rows that stay open after this session. None of them is marked DONE. "No command run" means the row was not started in this session, so there is no failed command to quote. Each row names what is missing so the next session can pick it up.

| Row | Item | Reason | Command that failed |
|---|---|---|---|
| 35 | org graph: Place, PARTICIPATES_IN, RECORDED_IN | Not started. Needs a population step that reads the cached mail and git into Place, PARTICIPATES_IN {since, last_at} and RECORDED_IN. The writer for PARTICIPATES_IN exists (core/memory/who_saw.py) but nothing calls it on real data. | No command run |
| 36 | org graph: SHARES edges built | Not started. `domain_hash` needs email domains, which the cache does not keep (only hashed ids). `same_thread_burst` needs thread structure that is not parsed yet. `creation_window` is NOT COMPUTED by design (no account data). Writing `eval/results/shares_build.json` needs the first two. | No command run |
| 40 | ecosystem_<id> graph: Foundation, HOSTED_BY, Campaign, TOUCHES | Partial. `HOSTED_BY` needs a public source that names the foundation hosting xz. None is in the cache, so writing an edge would invent one (against the number and data rules). Campaign and TOUCHES are not written yet. | No command run |
| 43 | playbook graph | Not started. `core/playbook/` is still empty. Depends on the learned-exception design (row 66). | No command run |
| 45 | Vector index on Span and full-text index on Span.text | Not started. The vector index needs a pinned local sentence-transformers model, which must be downloaded (its name and hash recorded). Not attempted in this session. The full-text DDL form is already verified in docs/VERIFIED.md (`CREATE FULLTEXT INDEX FOR (n:Span) ON (n.text)`). | No command run |
| 59 | Watcher (idempotent ingest, normals, SHARES, visibility) | Not started as a class. The pieces exist as scripts (ingest, core/normal/metrics.py, takeover checks). SHARES is blocked by row 36 and visibility edges by row 35. | No command run |
| 66 | Learned exceptions with safety rules and regression gate | Not started. `core/learning/` is empty. Needs a deterministic filler (docs/decisions/0007-learned-exception-filler.md, to be written), the four end states, and the gate calling the frozen detectors unchanged. | No command run |
| 80 | Learning proof (`verify-learning`, `chaos`) | Not started. Depends on rows 66 and 43. | No command run |
| 104 | It's fine button and learning result in thread | Not started. Depends on row 66. The browser check against the local app (eval/results/fine_browser_check.json) is also still to be done. | No command run |
| 120 | Playbook screen | Not started. `ui/src/Playbook.tsx` does not exist. Depends on rows 66 and 43. | No command run |
