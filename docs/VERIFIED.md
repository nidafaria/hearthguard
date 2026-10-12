# VERIFIED.md: Day 1 results

Day 1 (Oct 15) fills this table. Each row is one claim from the spec, checked against the running system or the live source. Nothing is marked verified before then.

| Item | Spec claim | Check | Result | Date | Status |
|---|---|---|---|---|---|
| FalkorDB image pin | `falkordb/falkordb:6.0.2` (newest 6.0.x tag on Docker Hub, pushed 2026-10-08) | `docker compose up -d`; `redis-cli PING`; `MODULE LIST`; `CONFIG GET dir` | PONG; module ver 60002; data dir `/var/lib/falkordb/data`; volume mounted there | 2026-10-12 | pinned at bootstrap |
