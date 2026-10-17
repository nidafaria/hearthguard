"""Public statements about who got commit or release rights in xz -> grant records.

Not a system log. Each statement is something a public page, a cached mail or a signed release
tag says. Dates are approximate: a statement that someone had a right on a date only bounds when
the right was given. Quotes are checked against the cached text before anything is written, and
people appear only as hashed ids (same hash as the git ingest: email, stripped, lower case).

Edges: a statement that names a privilege and a holder becomes a `grant` record. The statement
that only one person controlled the repositories becomes a `can_grant` record for that person.
Role statements with no named privilege (co-maintainer, supporting maintainer) are kept in the
file with edge = null and never become an edge.
"""

import html
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from core.graph.hashing import identifier_hash
from packs.oss import grants

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "raw"
GIT = RAW / "xz.git"
CACHE = RAW / "xz_statements"
TUKAANI_URL = "https://tukaani.org/xz-backdoor/"
SWTCH_URL = "https://research.swtch.com/xz-timeline"
MAIL_URL = "https://www.mail-archive.com/xz-devel@tukaani.org/msg{n:05d}.html"
LASSE_EMAIL = "lasse.collin@tukaani.org"
JIA_EMAIL = "jiat0218@gmail.com"
LABEL = "From public statements, not a system log. Dates approximate."


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _tag(name: str) -> tuple[int, str]:
    out = subprocess.run(
        [
            "git",
            "-C",
            str(GIT),
            "for-each-ref",
            f"refs/tags/{name}",
            "--format=%(taggerdate:unix)|%(subject)",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    at, subject = out.split("|", 1)
    return int(at), subject


def _iso(at: int) -> str:
    return datetime.fromtimestamp(at, UTC).strftime("%Y-%m-%d")


def unix_of(day: str) -> int:
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())


def build_statements(salt: bytes | None = None) -> list[dict]:
    """Every statement, with its quote verified against the cached source. Raises if one fails."""

    def h(ident: str) -> str:
        return identifier_hash(ident, salt=salt)

    lasse, jia = h(LASSE_EMAIL), h(JIA_EMAIL)
    sam = h("display_name:sam james")  # mail_cache fallback id: the message gives no address
    tuk, swt = _text(CACHE / "tukaani.html"), _text(CACHE / "swtch.html")
    mail = RAW / "mail" / "xz-devel"
    m571, m681 = _text(mail / "msg00571.html"), _text(mail / "msg00681.html")
    t_lasse, s_lasse = _tag("v5.0.0")
    t_jia, s_jia = _tag("v5.4.2")
    only_i = "Only I have had access to the main tukaani.org website"
    rows = [
        # (id, actor, privilege, edge, url, quote, date, quote_source_text, note)
        (
            "S1",
            jia,
            None,
            None,
            MAIL_URL.format(n=571),
            "is practically a co-maintainer already",
            "2022-06-29",
            m571,
            "Role statement by the maintainer; no privilege named.",
        ),
        (
            "S2",
            jia,
            None,
            None,
            SWTCH_URL,
            "it is a necessary step before granting maintainer access",
            "2022-10-28",
            swt,
            "Org membership step; the page says it grants nothing by itself.",
        ),
        (
            "S3",
            jia,
            "merge",
            "grant",
            SWTCH_URL,
            "we know they have commit access",
            "2022-12-30",
            swt,
            "Seen from a direct merge; the grant itself was on or before this.",
        ),
        (
            "S4",
            jia,
            "release",
            "grant",
            SWTCH_URL,
            "tags and builds their first release",
            _iso(t_jia),
            swt,
            f"Same day as signed git tag v5.4.2 ({s_jia!r}); the grant was on or before it.",
        ),
        (
            "S5",
            lasse,
            "release",
            "grant",
            "https://git.tukaani.org/xz.git",
            s_lasse,
            _iso(t_lasse),
            None,
            "Earliest signed release tag in the cached git (v5.0.0); holder on or before it.",
        ),
        (
            "S6",
            lasse,
            "release",
            "can_grant",
            TUKAANI_URL,
            only_i,
            "2024-04-02",
            tuk,
            "The page also names git.tukaani.org repositories. Date is the page's reinstatement "
            "note, not a grant.",
        ),
        (
            "S7",
            lasse,
            "merge",
            "can_grant",
            TUKAANI_URL,
            only_i,
            "2024-04-02",
            tuk,
            "Same statement as S6, applied to the merge privilege.",
        ),
        (
            "S8",
            jia,
            None,
            None,
            TUKAANI_URL,
            "Jia Tan only had access to things hosted on GitHub",
            "2024-04-02",
            tuk,
            "Limits that person's access; no edge.",
        ),
        (
            "S9",
            sam,
            None,
            None,
            MAIL_URL.format(n=681),
            "Sam James is now a supporting maintainer.",
            "2024-05-29",
            m681,
            "Role statement; no privilege named, so no edge.",
        ),
    ]
    out = []
    for sid, actor, priv, edge, url, quote, day, text, note in rows:
        if text is not None and quote not in text:
            raise ValueError(f"{sid}: quote not found in cached source")
        if len(quote.split()) >= 15:
            raise ValueError(f"{sid}: quote is 15 words or longer")
        out.append(
            {
                "id": sid,
                "actor": actor,
                "privilege": priv,
                "edge": edge,
                "source_url": url,
                "quote": quote,
                "date": day,
                "date_unix": unix_of(day),
                "date_approximate": day != "2024-05-29",
                "note": note,
            }
        )
    return out


def to_records(statements: list[dict]) -> list[dict]:
    recs = []
    for s in statements:
        if s["edge"] is None:
            continue
        rec = {
            "source": "public_statement",
            "kind": s["edge"],
            "actor": s["actor"],
            "privilege": s["privilege"],
            "ref": f"{s['source_url']}#{s['id']}",
        }
        if s["edge"] == "grant":
            rec["at"] = s["date_unix"]
        else:
            rec["approvals_required"] = 1
        recs.append(rec)
    return recs


def load_into_copy(client, src: str, dst: str, statements: list[dict]) -> grants.Mapped:
    """Copy `src` to `dst` (dropping an old `dst`), then write the statement edges into `dst`."""
    client.drop(dst)
    client.copy(src, dst)
    return grants.write_records(client, dst, to_records(statements))
