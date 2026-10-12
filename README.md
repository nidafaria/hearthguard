# Hearthguard

> Some attacks are too slow for anything that forgets.

Hearthguard is a trust memory for organisations. It is being built for the Graph Hacks hackathon (WeMakeDevs × FalkorDB). The full spec is in [docs/HEARTHGUARD.md](docs/HEARTHGUARD.md). Project rules are in [CLAUDE.md](CLAUDE.md).

## Setup (local)

```bash
cp .env.example .env          # fill in values locally; .env is git-ignored
make up                       # FalkorDB on localhost (pinned falkordb/falkordb:6.0.2)
uv sync                       # Python 3.11+ environment
make lint
make test
make down
```

On Windows without `make`, run `.\make.ps1 up`, `.\make.ps1 test`, and so on.

If port 6379 is already in use on your machine, set `FALKORDB_PORT` in `.env` (for example `FALKORDB_PORT=6380`).

## Status

Repository skeleton only. Application logic arrives in later steps.
