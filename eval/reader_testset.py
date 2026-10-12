"""Choose the 60-message Reader test set by a fixed rule, and write the labelling sheet.

Run:  python -m eval.reader_testset --preview            show the pools and what each policy picks
      python -m eval.reader_testset --shortfall keep     build the test set and the sheet
(or set READER_SHORTFALL; see below)

The rule, with no hand-picking:
  Pool       cached xz-devel messages dated 2021-01-01 to 2024-12-31 (UTC).
  Exclude    the 20 spot-check messages (eval/results/reader_sample.json).
  Stratify   by calendar year, 15 messages from each of 2021, 2022, 2023 and 2024.
  Within a year, sort by message id and take every k-th, k = floor(pool size / 15), starting at the
  first id, until 15 are taken.

The rule cannot be met when a year has fewer than 15 messages: the list was almost silent in 2023.
The builder then REFUSES to continue until a policy is chosen explicitly:
  keep      a short year contributes all of its messages; the set is smaller than 60
  top-up    as keep, then the missing messages are taken from the unchosen messages of all years,
            sorted by id, every k-th from the first id (k = floor(unchosen / missing))

The sheet holds the cleaned text the Reader will be given (the same cleaning as the spot check), so
a person labels exactly what the Reader sees. Names of people who were mentioned but never posted
cannot be known from the list, so they are read from a local, git-ignored file,
data/raw/extra_redactions.txt (one name or handle per line), and replaced by [person]. The names are
never written to the repository.

The sheet is never overwritten once a person has filled in any label.
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from core.claims import reader
from eval import reader_freeze as rf
from eval import reader_sheet as sheet
from eval import reader_spotcheck as rs
from packs.oss import mail_cache

RESULTS = Path(__file__).resolve().parent / "results"
TESTSET_PATH = sheet.TESTSET_PATH
SHEET_PATH = sheet.SHEET_PATH
GUIDE_PATH = RESULTS / "reader_labelling_guide.md"
EXTRA_FILE = mail_cache.RAW_ROOT.parents[1] / "extra_redactions.txt"

WINDOW = ("2021-01-01", "2024-12-31")
YEARS = ("2021", "2022", "2023", "2024")
PER_YEAR = 15
POLICIES = ("keep", "top-up")

EMAIL_SHAPE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w\-]+")

RULE_TEXT = (
    "Pool: cached xz-devel messages dated 2021-01-01 to 2024-12-31 (UTC), minus the 20 spot-check "
    "messages. Stratified by year, 15 per year. "
    "Within a year: sort by message id, take every k-th, "
    "k = floor(pool size / 15), starting at the first id."
)


class PoolTooSmall(RuntimeError):
    """A year has fewer than 15 messages and no shortfall policy was chosen."""


# ----------------------------------------------------------------------------- selection (pure)
def year_pools(rows: list[dict], exclude: set[int]) -> dict[str, list[int]]:
    pools: dict[str, list[int]] = {y: [] for y in YEARS}
    for r in rows:
        day = (r.get("date_utc") or "")[:10]
        if r["status"] == 200 and WINDOW[0] <= day <= WINDOW[1] and r["msg"] not in exclude:
            pools[day[:4]].append(r["msg"])
    return {y: sorted(ids) for y, ids in pools.items()}


def pick_every_kth(ids: list[int], n: int) -> tuple[list[int], int]:
    """Every k-th id from the first, k = floor(len / n), until n are taken."""
    k = len(ids) // n
    if k == 0:
        raise PoolTooSmall(f"{len(ids)} ids, fewer than {n}")
    return ids[::k][:n], k


def select(rows: list[dict], exclude: set[int], shortfall: str | None = None) -> dict:
    """Pick the test set. Deterministic: the same rows and policy always give the same answer."""
    if shortfall not in (None, *POLICIES):
        raise ValueError(f"shortfall policy must be one of {POLICIES}")
    pools = year_pools(rows, exclude)
    by_year: dict[str, list[int]] = {}
    k_by_year: dict[str, int | None] = {}
    short: dict[str, int] = {}
    for year in YEARS:
        ids = pools[year]
        if len(ids) >= PER_YEAR:
            by_year[year], k_by_year[year] = pick_every_kth(ids, PER_YEAR)
        else:
            by_year[year], k_by_year[year] = list(ids), None
            short[year] = PER_YEAR - len(ids)
    if short and shortfall is None:
        raise PoolTooSmall(
            "; ".join(f"{y} has {len(pools[y])} messages, 15 needed" for y in short)
            + f". Choose a policy: {' or '.join(POLICIES)}."
        )
    topup: list[int] = []
    if short and shortfall == "top-up":
        chosen = {i for ids in by_year.values() for i in ids}
        leftover = sorted(i for ids in pools.values() for i in ids if i not in chosen)
        need = sum(short.values())
        topup = leftover[:: len(leftover) // need][:need]
    ids = sorted({i for v in by_year.values() for i in v} | set(topup))
    return {
        "pool_sizes": {y: len(v) for y, v in pools.items()},
        "k_by_year": k_by_year,
        "by_year": by_year,
        "shortfall": short,
        "shortfall_policy": shortfall if short else None,
        "topup_ids": topup,
        "ids": ids,
    }


# ----------------------------------------------------------------------------- privacy
def load_extra_names(path: Path = EXTRA_FILE) -> list[str]:
    if not path.exists():
        return []
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def _name_re(name: str) -> str:
    return r"\b" + r"\s+".join(map(re.escape, name.split())) + r"\b"


def apply_extra(text: str, names: list[str]) -> tuple[str, int]:
    count = 0
    for name in sorted(names, key=len, reverse=True):
        text, n = re.subn(_name_re(name), "[person]", text, flags=re.I)
        count += n
    return text, count


def leaks(text: str, redactor: reader.Redactor, extra: list[str]) -> list[str]:
    """What is still in the text that must not be: an email, a URL, or a known name."""
    found = []
    if EMAIL_SHAPE.search(text):
        found.append("an email-shaped string")
    if "http://" in text or "https://" in text:
        found.append("a URL")
    for name in [*redactor.full_names, *redactor.tokens, *extra]:
        if re.search(_name_re(name), text, flags=re.I if name in extra else 0):
            found.append("a known name")
            break
    return found


def prepare_text(n: int, redactor: reader.Redactor, extra: list[str]):
    head, author_hash, clean = rs.prepare(n, redactor)
    text, extra_n = apply_extra(clean.text, extra)
    return head, author_hash, text.strip(), clean.emails_replaced + clean.names_replaced + extra_n


# ----------------------------------------------------------------------------- building
GUIDE = """# How to label the Reader test set

The sheet is `eval/results/reader_labelsheet.csv`. You are the labeller; the Reader has not been run
on these messages.

**What to label.** For each message, for each of the seven claim kinds, write `yes` or `no`:
does the AUTHOR of the message say something of that kind in their own words, in the
`cleaned_text` column? Every cell must be `yes` or `no`. An empty cell blocks scoring.

**Do not edit `cleaned_text`.** It is exactly what the Reader will be shown, and the scorer refuses
a sheet whose text was changed. Use the `notes` column for doubts. Lines quoted from earlier
messages were already removed, so label only what is left. `[person]`, `[author]`, `[email]` and
`[url]` stand for removed names, addresses and links.

**The seven kinds** (the same wording the Reader was given):

- PRESSURE: pushes the maintainer to act faster or differently, or complains that they are too slow.
- URGENCY: stresses time pressure or a deadline.
- VOUCH: endorses a person as trustworthy or competent, or recommends them for a role.
- REQUESTS_PRIVILEGE: asks to be given rights over the project (commit, release, maintainer role).
- CAPACITY_STATEMENT: says that someone's time, resources or ability to maintain is limited.
- CHANGE_REQUEST: asks that who maintains or controls the project change (add or replace a
  maintainer, someone else should take over). A routine request to review or apply a patch is NOT
  this kind.
- HANDOVER_ANNOUNCEMENT: announces that responsibility or access has been, or is being, handed over.

A message can have none of them, one, or several. Most messages will be all `no`.

**Save the file as CSV (UTF-8)** under the same name. Then run `make.ps1 reader-score`.
"""


def build(shortfall: str | None, preview: bool = False) -> int:
    frozen = rf.load_frozen()
    if frozen is None or rf.mismatches(frozen):
        print(
            "The Reader is not frozen, or has changed since the freeze. "
            "Run: python -m eval.reader_freeze"
        )
        return 1
    rows = mail_cache.build_index(mail_cache.RAW_ROOT)
    spot = {int(i.removeprefix("msg")) for i in json.loads(rs.SAMPLE_PATH.read_text())["ids"]}

    if preview:
        _preview(rows, spot)
        return 0
    try:
        chosen = select(rows, spot, shortfall)
    except PoolTooSmall as e:
        print(f"Cannot build the test set: {e}")
        print("Re-run with --shortfall keep or --shortfall top-up (or set READER_SHORTFALL).")
        return 2
    if rf.labels_exist():
        print("The sheet already has labels from a person. Not overwriting it.")
        return 3

    redactor = rs.build_redactor()
    extra = load_extra_names()
    messages, problems, empties = [], [], []
    texts: dict[int, str] = {}
    for n in chosen["ids"]:
        head, author_hash, text, _ = prepare_text(n, redactor, extra)
        found = leaks(text, redactor, extra)
        if found:
            problems.append(f"{rs.msg_id(n)}: {', '.join(found)}")
        if not text:
            empties.append(rs.msg_id(n))
        texts[n] = text
        messages.append(
            {
                "message_id": rs.msg_id(n),
                "year": head["date"].strftime("%Y"),
                "date_utc": head["date"].isoformat().replace("+00:00", "Z"),
                "author_hash": author_hash,
                "text_chars": len(text),
                "text_sha256": sheet.text_hash(text),
            }
        )
    if problems:
        print("Stopping: the cleaned text still holds something it must not:")
        print("\n".join(problems))
        return 4

    doc = {
        "rule": RULE_TEXT,
        "window": list(WINDOW),
        "per_year_target": PER_YEAR,
        "pool_sizes": chosen["pool_sizes"],
        "k_by_year": chosen["k_by_year"],
        "shortfall": chosen["shortfall"],
        "shortfall_policy": chosen["shortfall_policy"],
        "topup_ids": [rs.msg_id(i) for i in chosen["topup_ids"]],
        "excluded_spotcheck_ids": [rs.msg_id(i) for i in sorted(spot)],
        "count": len(chosen["ids"]),
        "ids_by_year": {y: [rs.msg_id(i) for i in v] for y, v in chosen["by_year"].items()},
        "ids": [rs.msg_id(i) for i in chosen["ids"]],
        "empty_text_ids": empties,
        "reader_frozen_version": frozen["version"],
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "messages": messages,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    TESTSET_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    with SHEET_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(sheet.COLUMNS)
        for m in messages:
            n = int(m["message_id"].removeprefix("msg"))
            w.writerow([m["message_id"], m["year"], texts[n], *[""] * len(sheet.KINDS), ""])
    GUIDE_PATH.write_text(GUIDE, encoding="utf-8")
    print(
        f"test set: {doc['count']} messages | pools {doc['pool_sizes']} | "
        f"policy {doc['shortfall_policy']}"
    )
    print(f"wrote {TESTSET_PATH.name}, {SHEET_PATH.name} (labels empty), {GUIDE_PATH.name}")
    if empties:
        print(f"messages with no text left after cleaning: {empties}")
    return 0


def _preview(rows: list[dict], spot: set[int]) -> None:
    pools = year_pools(rows, spot)
    print("pool sizes after excluding the spot check:", {y: len(v) for y, v in pools.items()})
    for policy in (None, *POLICIES):
        try:
            c = select(rows, spot, policy)
        except PoolTooSmall as e:
            print(f"\npolicy none: refused ({e})")
            continue
        print(
            f"\npolicy {policy}: {len(c['ids'])} messages; per year "
            f"{ {y: len(v) for y, v in c['by_year'].items()} }; top-up {len(c['topup_ids'])}"
        )
        print("  k by year:", c["k_by_year"], "| ids:", c["ids"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--shortfall", choices=POLICIES, default=os.environ.get("READER_SHORTFALL") or None
    )
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args(argv)
    return build(args.shortfall, args.preview)


if __name__ == "__main__":
    sys.exit(main())
