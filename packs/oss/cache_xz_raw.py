"""Cache public xz data and describe the cache. Run: python -m packs.oss.cache_xz_raw <command>

  mail        cache the xz-devel messages (2021 to 2024, plus msg00512 to msg00571), write the index
  github      cache pull requests, their reviews and comments, and the MAINTAINERS and CODEOWNERS
              commit history. Slow without a GITHUB_TOKEN (60 an hour); safe to stop and rerun
  inventory   write eval/results/xz_raw_inventory.json from what is cached (fetches nothing)
  status      print how many GitHub requests are still missing (fetches nothing)

Nothing here touches the graph. The token is never printed.
"""

import argparse
import sys

from packs.oss import github_cache, mail_cache, raw_inventory
from packs.oss.raw_cache import Fetcher


def run_mail() -> int:
    fetcher = Fetcher(mail_cache.RAW_ROOT, min_interval_s=1.0)
    try:
        summary = mail_cache.cache_messages(fetcher)
    finally:
        fetcher.close()
    index = mail_cache.write_index()
    print(
        f"{summary}; network requests {fetcher.network_requests}, from cache {fetcher.cache_hits}"
    )
    print(f"index written: {index.relative_to(index.parents[3])}")
    return 0


def run_github() -> int:
    print(f"GitHub token configured: {github_cache.github_token() is not None}")  # a yes or no only
    fetcher = github_cache.make_fetcher(min_interval_s=0.5)
    try:
        summary = github_cache.crawl(fetcher)
    finally:
        fetcher.close()
    print(summary)
    return 0


def run_status() -> int:
    fetcher = github_cache.make_fetcher(min_interval_s=0)
    todo = github_cache.missing(fetcher)
    fetcher.close()
    by_group: dict[str, int] = {}
    for r in todo:
        by_group[r.group] = by_group.get(r.group, 0) + 1
    print(f"pull requests cached: {len(github_cache.pr_numbers(fetcher))}")
    print(f"GitHub requests still missing (at least): {len(todo)} {by_group}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["mail", "github", "inventory", "status"])
    args = ap.parse_args(argv)
    if args.command == "mail":
        return run_mail()
    if args.command == "github":
        return run_github()
    if args.command == "status":
        return run_status()
    inv = raw_inventory.write_inventory()
    print(f"wrote {raw_inventory.OUT}")
    print(
        f"GitHub complete: {inv['github']['complete']}; mail messages in scope: "
        f"{inv['mailing_list']['messages_in_scope']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
