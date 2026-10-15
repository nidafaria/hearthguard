# Blockers, row 40 (ecosystem graph: Foundation, HOSTED_BY, Campaign, TOUCHES)

Spec §6.2. Loaded into `ecosystem_xz` only from records already in `data/raw/`. Reloaded twice: counts identical (`eval/results/ecosystem_load.json`, `identical: true`).

## Added
- `Org` (2): `tukaani-project/xz` (place `xz-git`) and `google/oss-fuzz` (place `oss-fuzz`). Source: the owner/repo in the cached GitHub API URLs of those places.
- `Campaign` (1): id `CVE-2024-3094`, the id cited in the cached records (`data/raw/mail/xz-devel/msg00681.html`, `data/raw/ecosystem/gh_ossfuzz_pr_10667_comments.json`). `moves` is the count of the persona's signals in the loaded records.
- `TOUCHES` (2): Campaign to each Org where the persona has signals. `signals` is that count.

## Left out
- **Foundation and HOSTED_BY: no public source in the cache.** No cached record names a foundation that hosts xz, oss-fuzz, the kernel list, Debian or Launchpad. Writing one from general knowledge would be an unsourced claim.
- **Campaign `status`: no public source.** No cached record states whether the campaign is ongoing or closed.
- **Org for `lkml`, `debian-bts`, `launchpad`, `xz-devel`:** the cached records of those places name no owning organisation, so no Org and no TOUCHES edge.

## Caveat
Calling the persona's activity a "campaign" is the project's reading. The cache holds the CVE id and the persona's actions, not a record that says "campaign". No detector or gap query reads these nodes.
