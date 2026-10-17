# Blockers s2: Job B rows (about 30 projects, false-alarm projects, census, foundations, hosting)

Checked 2026-10-18 on branch coding/s2-data. Nothing was invented, no project list was chosen, no
network ingest was run for these rows. Spec refs are to docs/HEARTHGUARD.md and docs/FREEZE.md.

| Row | Item | Real public source? | Why it is not built |
|---|---|---|---|
| 24 | Foundation view across projects | One fact only | The only sourced foundation link found is Debian listed on https://www.spi-inc.org/projects/ (line: "[Debian](debian)"). xz (Tukaani), oss-fuzz (Google), Launchpad (Canonical) have no foundation page that says so; the kernel list was not sourced. A view across projects needs more than one. |
| 40 | Foundation, HOSTED_BY | One fact only | `HOSTED_BY` would join an Org to a Foundation. The place `debian-bts` has no Org node (`eval/results/blockers_40.md`: its cached records name no owning organisation), so the SPI line has nothing to attach to. Row stays PARTIAL. |
| 42, 88, 95 | census_<date>, `make census N=100`, npm census ingest | Probably (public npm registry and public high-impact lists), not verified | `docs/FREEZE.md` section 7: census population is **NOT FROZEN**; source name and URL are TBD. Picking the list now, after the event started, breaks the anti-hindsight rule (spec 10.1). The takeover-cost rule for npm maintainers is still PROPOSED (`docs/decisions/0001-outsider-edges.md`), so any "K of N have cost 1" figure would depend on an unsettled rule. Owner must fill the source and freeze it first. |
| 119 | Census screen data | No | Depends on rows 88/95. |
| 86 | Ownership accuracy, about 30 projects | Partly (GitHub API, read-only) | Needs the project list; `docs/FREEZE.md` section 6 selection rule is PROPOSED and the list in `data/sources.yaml` is not written. It also needs a built pipeline (`make verify-ownership` is not built) and a hand check of MAINTAINERS/CODEOWNERS truth. |
| 85, 89 | Hardening / false-alarm study on false-alarm projects | Partly (GitHub API, read-only) | Same unfrozen list (section 6). `make false-positives` is not built (`eval/results/blockers_I.md`). Running detectors on a list chosen after the fact would be tuning against it. |

What exists if the owner freezes the lists: a GitHub token in `.env` (5,000 requests/hour) and the
public npm registry (`packs/oss/npm.py` parses a packument). Both are read-only.
