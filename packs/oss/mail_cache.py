"""Cache the public xz-devel mailing-list archive under data/raw/mail/xz-devel/ (public data only).

Source: the public mail-archive.com mirror of the list. Message numbers run in time order, so the
2021 to 2024 range is found by binary search on the message date, then every message in it is
fetched, plus msg00512 to msg00571 (the 2021-2022 messages the spec names).

Each page is saved as msgNNNNN.html with a `.meta.json` sidecar (URL, fetch time). The index built
from them (index.json) holds no name and no email. An author email is hashed if the page shows one;
the archive shows only a display name in the header, so that name is hashed instead, in a separate
hash namespace so a name hash can never be mistaken for an email hash. The message body pages keep
the text as published; the whole directory is git-ignored.
"""

import html as htmllib
import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from core.graph.hashing import identifier_hash
from packs.oss.raw_cache import Fetcher

LIST_ADDRESS = "xz-devel@tukaani.org"
BASE = f"https://www.mail-archive.com/{LIST_ADDRESS}/"
RAW_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "mail" / "xz-devel"
EXPLICIT = range(512, 572)  # msg00512 to msg00571
WINDOW_START = datetime(2021, 1, 1, tzinfo=UTC)
WINDOW_END = datetime(2025, 1, 1, tzinfo=UTC)  # exclusive: the window is 2021-01-01 to 2024-12-31
GAP_PROBES = 6  # how many following message numbers to try when one is missing


def msg_name(n: int) -> str:
    return f"msg{n:05d}.html"


def msg_url(n: int) -> str:
    return BASE + msg_name(n)


def in_scope(n: int, date: datetime | None) -> bool:
    if n in EXPLICIT:
        return True
    return date is not None and WINDOW_START <= date < WINDOW_END


# ------------------------------------------------------------------ parsing
def _text(fragment: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def parse_message(page: str) -> dict:
    """Subject, sender display name, an author email if the header shows one, and the date (UTC)."""
    head_start = page.find('<div class="msgHead"')
    head = (
        page[head_start : page.find('itemprop="articleBody"', head_start)]
        if head_start >= 0
        else ""
    )

    subject = re.search(r'<span class="subject".*?<span itemprop="name">(.*?)</span>', head, re.S)
    sender = re.search(
        r'<span class="sender[^"]*".*?<span itemprop="name">(.*?)</span>', head, re.S
    )
    raw_date = re.search(r'<span class="date"[^>]*>(.*?)</span>', head, re.S)
    email = re.search(r'mailto:([^"?\s<>]+)', head) or re.search(
        r'itemprop="email"[^>]*>([^<\s]+)', head
    )

    date = None
    if raw_date:
        try:
            date = parsedate_to_datetime(_text(raw_date.group(1))).astimezone(UTC)
        except (TypeError, ValueError):
            date = None
    return {
        "subject": _text(subject.group(1)) if subject else None,
        "sender_name": _text(sender.group(1)) if sender else None,
        "sender_email": htmllib.unescape(email.group(1)) if email else None,
        "date": date,
    }


def author_hash(email: str | None, name: str | None) -> tuple[str | None, str | None]:
    """(hash, basis). An email is hashed if there is one; otherwise the display name."""
    if email:
        return identifier_hash(email.strip().lower()), "email"
    if name:
        return identifier_hash("display_name:" + name.strip().lower()), "display_name"
    return None, None


# ------------------------------------------------------------------ fetching
def message_date(fetcher: Fetcher, n: int) -> datetime | None:
    entry = fetcher.get(msg_url(n), msg_name(n))
    if entry.body_path is None:
        return None
    return parse_message(entry.text())["date"]


def _date_near(fetcher: Fetcher, n: int, top: int) -> datetime | None:
    """The date of message n, or of the next one that exists if n is missing."""
    for k in range(GAP_PROBES):
        if n + k > top:
            return None
        d = message_date(fetcher, n + k)
        if d is not None:
            return d
    return None


def _exists_near(fetcher: Fetcher, n: int) -> bool:
    return any(message_date(fetcher, n + k) is not None for k in range(GAP_PROBES))


def last_message_number(fetcher: Fetcher) -> int:
    """The newest message number. Doubles until nothing exists nearby, then bisects.

    A number counts as present if it or one of the next few exists, so a single missing message
    cannot end the search early.
    """
    hi = 1
    while _exists_near(fetcher, hi * 2):
        hi *= 2
    lo, up = hi, hi * 2  # something exists near lo; nothing exists near up
    while up - lo > 1:
        mid = (lo + up) // 2
        if _exists_near(fetcher, mid):
            lo = mid
        else:
            up = mid
    return max(k for k in range(lo, lo + GAP_PROBES) if message_date(fetcher, k) is not None)


def first_at_or_after(fetcher: Fetcher, target: datetime, top: int) -> int:
    """Smallest message number whose date is on or after target (top + 1 if there is none)."""
    lo, hi = 1, top
    while lo <= hi:
        mid = (lo + hi) // 2
        d = _date_near(fetcher, mid, top)
        if d is not None and d >= target:
            hi = mid - 1
        else:
            lo = mid + 1
    return lo


def plan_range(fetcher: Fetcher) -> tuple[int, int, int]:
    """(first, last, top): the message numbers spanning the window, and the newest number."""
    top = last_message_number(fetcher)
    first = first_at_or_after(fetcher, WINDOW_START, top)
    last = first_at_or_after(fetcher, WINDOW_END, top) - 1
    return first, last, top


def cache_messages(fetcher: Fetcher, log=print) -> dict:
    first, last, top = plan_range(fetcher)
    wanted = sorted(set(range(first, last + 1)) | set(EXPLICIT))
    log(f"newest message is {top}; window msg{first:05d} to msg{last:05d}; {len(wanted)} to cache")
    for i, n in enumerate(wanted, start=1):
        fetcher.get(msg_url(n), msg_name(n))
        if i % 25 == 0 or i == len(wanted):
            log(f"messages cached: {i}/{len(wanted)}")
    return {"first": first, "last": last, "top": top, "wanted": len(wanted)}


# ------------------------------------------------------------------ the index
def build_index(root: Path = RAW_ROOT) -> list[dict]:
    """One row per cached message page: number, date, subject, hashed author. No name, no email."""
    rows = []
    for meta_path in sorted(root.glob("msg*.html.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        name = meta_path.name.removesuffix(".meta.json")
        if meta["status"] == 200 and not (root / name).is_file():
            continue  # a sidecar whose page is gone is not a cached message
        n = int(re.fullmatch(r"msg(\d+)\.html", name).group(1))
        row = {
            "msg": n,
            "file": name,
            "status": meta["status"],
            "fetched_at_utc": meta["fetched_at_utc"],
        }
        if meta["status"] == 200:
            parsed = parse_message((root / name).read_text(encoding="utf-8", errors="replace"))
            h, basis = author_hash(parsed["sender_email"], parsed["sender_name"])
            date = parsed["date"]
            row |= {
                "date_utc": date.isoformat().replace("+00:00", "Z") if date else None,
                "subject": parsed["subject"],
                "author_hash": h,
                "author_hash_basis": basis,
                "in_scope": in_scope(n, date),
            }
        rows.append(row)
    return rows


def write_index(root: Path = RAW_ROOT) -> Path:
    rows = build_index(root)
    out = root / "index.json"
    out.write_text(
        json.dumps({"source": "xz-devel", "messages": rows}, indent=1) + "\n", encoding="utf-8"
    )
    return out
