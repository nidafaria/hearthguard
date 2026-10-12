"""Task 2: parse the cached records into events, and resolve who is who without keeping names.

Reads only data/raw/ecosystem/ (written by fetch.py). For each record it extracts the date, the
actor's role, and the action. Nothing is typed in by hand except the role vocabulary, and each
role is assigned from a field in the record (see `ROLE_EVIDENCE`).

Identity rules (docs/HEARTHGUARD.md §6.2):
  - Two observations with the same email hash or the same platform handle are the same identity.
  - Two identities with the same display-name hash get a weaker SAME_AS edge (evidence
    `persona_name`, strength 0.5). A name alone never merges anyone.
  - Only the persona "Jia Tan" is ever kept as a name, and only its public handles are kept.
    Every other person is a hash plus a role.
"""

import html
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from core.graph.hashing import identifier_hash, load_salt
from packs.oss.ecosystem.fetch import RAW_DIR, TOKEN_RE

PERSONA = "Jia Tan"
CUTOFF = datetime(2024, 3, 29, 23, 59, 59, tzinfo=UTC)  # through the day the backdoor was found

ROLE_OSSFUZZ = "oss-fuzz reviewer"
ROLE_UPSTREAM = "xz upstream maintainer"
ROLE_KERNEL = "Linux kernel reviewer"
ROLE_DEB_MAINT = "Debian package maintainer"
ROLE_UBUNTU = "Ubuntu developer"
# Roles that count as "watching" the place where they acted (the WATCHES edge, §6.2).
WATCHING_ROLES = {ROLE_OSSFUZZ, ROLE_UPSTREAM, ROLE_KERNEL, ROLE_DEB_MAINT, ROLE_UBUNTU}

# Where each role label comes from. Printed into the output so the labels are not a hidden choice.
ROLE_EVIDENCE = {
    ROLE_OSSFUZZ: "the user who approved and merged the pull request in google/oss-fuzz",
    ROLE_UPSTREAM: "the sender of the kernel patch that says it is the upstream maintainer, and "
    "the xz committer of the same display name",
    ROLE_KERNEL: "an author of a reply in the kernel mailing-list thread of the maintainer patch",
    ROLE_DEB_MAINT: "the person named as 'Maintainer for xz-utils' on the Debian bug page",
    ROLE_UBUNTU: "the user who changed the package's bug status in the Launchpad activity log",
}

PLACES = {
    "xz-devel": "list",
    "xz-git": "repo",
    "oss-fuzz": "ci",
    "lkml": "list",
    "debian-bts": "tracker",
    "launchpad": "tracker",
}

# A record is the thing a decision is about. Text that cites another record links to it.
RECORD_PATTERNS = {
    "oss-fuzz PR 9960": [r"\b6403e933\b", r"oss-fuzz/pull/9960", r"#9960\b"],
    "oss-fuzz PR 10667": [r"\bd2e42b2e\b", r"oss-fuzz/pull/10667", r"#10667\b"],
    "debian bug 1067708": [r"\b1067708\b"],
    "launchpad bug 2059417": [r"\b2059417\b"],
}


def _epoch(dt: datetime) -> int:
    return int(dt.astimezone(UTC).timestamp())


def _iso(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_to_epoch(s: str) -> int:
    return _epoch(datetime.fromisoformat(s.replace("Z", "+00:00")))


def _text(name: str) -> str:
    return (RAW_DIR / name).read_text(encoding="utf-8")


def _json(name: str):
    return json.loads(_text(name))


def _plain(name: str) -> str:
    t = re.sub(r"<(script|style).*?</\1>", "", _text(name), flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", t))


def _meta_url(name: str) -> str:
    return json.loads((RAW_DIR / f"{name}.meta.json").read_text(encoding="utf-8"))["url"]


@dataclass
class Obs:
    """One sighting of a person. Names stay in memory only; outputs carry hashes."""

    name: str | None = None
    email_hash: str | None = None
    handle: tuple[str, str] | None = None  # (platform, handle)


@dataclass
class Event:
    source_id: str
    source_file: str
    place: str
    record: str
    kind: str
    action: str
    at: int
    role: str
    obs: Obs
    ref: str
    index: int = 0
    refs_records: list[str] = field(default_factory=list)
    event_id: str = ""


class Registry:
    """Union-find over exact keys (email hash, handle hash); name hashes link weakly."""

    def __init__(self, salt: bytes) -> None:
        self.salt = salt
        self.parent: dict[str, str] = {}
        self.names: dict[str, set[str]] = {}  # cluster key -> display names (in memory only)
        self.handles: dict[str, set[tuple[str, str]]] = {}
        self.all_names: set[str] = set()

    def _h(self, s: str) -> str:
        return identifier_hash(s, salt=self.salt)

    def find(self, k: str) -> str:
        self.parent.setdefault(k, k)
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def keys_of(self, o: Obs) -> list[str]:
        keys = []
        if o.email_hash:
            keys.append("email:" + o.email_hash)
        if o.handle:
            keys.append("handle:" + self._h(f"handle:{o.handle[0]}:{o.handle[1].lower()}"))
        if not keys and o.name:
            keys.append("name:" + self._h("name:" + o.name.casefold()))
        return keys

    def add(self, o: Obs) -> None:
        keys = self.keys_of(o)
        if o.name:
            self.all_names.add(o.name)
        for k in keys:
            self.find(k)
        for k in keys[1:]:
            self.union(keys[0], k)
        if keys:
            root = self.find(keys[0])
            self.names.setdefault(root, set())
            self.handles.setdefault(root, set())

    def finish(self, observations: list[Obs]) -> None:
        """Second pass: attach names and handles to the final cluster roots."""
        self.names, self.handles = {}, {}
        for o in observations:
            keys = self.keys_of(o)
            if not keys:
                continue
            root = self.find(keys[0])
            if o.name:
                self.names.setdefault(root, set()).add(o.name)
            if o.handle:
                self.handles.setdefault(root, set()).add(o.handle)

    def hid(self, o: Obs) -> str:
        keys = self.keys_of(o)
        return self._h("identity:" + self.find(keys[0]))

    def name_hash(self, name: str) -> str:
        return self._h("name:" + name.casefold())

    def cluster_name_hashes(self, o: Obs) -> set[str]:
        root = self.find(self.keys_of(o)[0])
        return {self.name_hash(n) for n in self.names.get(root, set())}


# ---------------------------------------------------------------- per-source parsers
def _tok(s: str) -> str | None:
    m = TOKEN_RE.search(s)
    return m.group(1) if m else None


def _name_before_token(s: str) -> str | None:
    m = re.match(r"\s*\"?([^<\[\"]*?)\"?\s*<?\[email-hash:", s)
    name = m.group(1).strip() if m else None
    return name or None


def _refs_in(text: str, own_record: str) -> list[str]:
    found = []
    for rec, pats in RECORD_PATTERNS.items():
        if rec != own_record and any(re.search(p, text) for p in pats):
            found.append(rec)
    return sorted(found)


def parse_oss_fuzz() -> list[Event]:
    events: list[Event] = []
    for sha, pr in (("6403e933", 9960), ("d2e42b2e", 10667)):
        record = f"oss-fuzz PR {pr}"
        patch = _text(f"oss_fuzz_{sha}.patch")
        api = _json(f"gh_ossfuzz_commit_{sha}.json")
        login = api["author"]["login"]
        m = re.search(r"^From: (.*)$", patch, re.M)
        author_name = _name_before_token(m.group(1)) if m else None
        email_hash = _tok(m.group(1)) if m else None
        d = re.search(r"^Date: (.*)$", patch, re.M)
        subject = re.search(r"^Subject: \[PATCH\] (.*)$", patch, re.M).group(1)
        author = Obs(author_name, email_hash, ("github", login))
        events.append(
            Event(
                f"oss_fuzz_{sha}",
                f"oss_fuzz_{sha}.patch",
                "oss-fuzz",
                record,
                "commit",
                f"commit to google/oss-fuzz: {subject}",
                _epoch(parsedate_to_datetime(d.group(1))),
                "contributor",
                author,
                f"oss-fuzz/commit/{sha}",
                refs_records=_refs_in(patch, record),
            )
        )
        pull = _json(f"gh_ossfuzz_pr_{pr}.json")
        reviews = _json(f"gh_ossfuzz_pr_{pr}_reviews.json")
        comments = _json(f"gh_ossfuzz_pr_{pr}_comments.json")
        merger = pull["merged_by"]["login"]
        pid = f"gh_ossfuzz_pr_{pr}"
        events.append(
            Event(
                pid,
                f"{pid}.json",
                "oss-fuzz",
                record,
                "pr_opened",
                f"pull request opened in google/oss-fuzz (#{pr})",
                _iso_to_epoch(pull["created_at"]),
                "contributor",
                Obs(None, None, ("github", pull["user"]["login"])),
                f"oss-fuzz#{pr}",
            )
        )
        events.append(
            Event(
                pid,
                f"{pid}.json",
                "oss-fuzz",
                record,
                "pr_merged",
                f"pull request merged in google/oss-fuzz (#{pr})",
                _iso_to_epoch(pull["merged_at"]),
                ROLE_OSSFUZZ,
                Obs(None, None, ("github", merger)),
                f"oss-fuzz#{pr}",
            )
        )
        for r in reviews:
            who = r["user"]["login"]
            events.append(
                Event(
                    f"{pid}_reviews",
                    f"{pid}_reviews.json",
                    "oss-fuzz",
                    record,
                    "pr_review",
                    f"pull request review: {r['state'].lower()}",
                    _iso_to_epoch(r["submitted_at"]),
                    ROLE_OSSFUZZ if who == merger else "pull request commenter",
                    Obs(None, None, ("github", who)),
                    f"oss-fuzz#{pr}/review/{r['id']}",
                )
            )
        for c in comments:
            who = c["user"]["login"]
            if c["user"].get("type") == "Bot":
                continue
            events.append(
                Event(
                    f"{pid}_comments",
                    f"{pid}_comments.json",
                    "oss-fuzz",
                    record,
                    "pr_comment",
                    "comment on pull request",
                    _iso_to_epoch(c["created_at"]),
                    ROLE_OSSFUZZ if who == merger else "pull request commenter",
                    Obs(None, None, ("github", who)),
                    f"oss-fuzz#{pr}/comment/{c['id']}",
                )
            )
    return events


def _lkml_fields(name: str) -> tuple[str, str, int]:
    t = _plain(name)
    m_from = re.search(r"From([A-Z][^<\n]*?) <", t)
    m_date = re.search(r"Date([A-Z][a-z]{2}, \d+ [A-Z][a-z]{2} \d{4} [\d:]+ [+-]\d{4})", t)
    return m_from.group(1).strip(), t, _epoch(parsedate_to_datetime(m_date.group(1)))


def parse_lkml() -> list[Event]:
    record = "lkml 2024/3/20/1008"
    sender, text, at = _lkml_fields("lkml_2024_3_20_1008.html")
    sob = re.search(rf"Signed-off-by: {re.escape(sender)} <\[email-hash:([0-9a-f]{{64}})\]>", text)
    rev = re.search(rf"Reviewed-by: {re.escape(PERSONA)} <\[email-hash:([0-9a-f]{{64}})\]>", text)
    events = [
        Event(
            "lkml_2024_3_20_1008",
            "lkml_2024_3_20_1008.html",
            "lkml",
            record,
            "patch_sent",
            "kernel patch sent adding the xz maintainers to MAINTAINERS",
            at,
            ROLE_UPSTREAM,
            Obs(sender, sob.group(1) if sob else None),
            "lkml/2024/3/20/1008",
            refs_records=_refs_in(text, record),
        )
    ]
    if rev:
        events.append(
            Event(
                "lkml_2024_3_20_1008",
                "lkml_2024_3_20_1008.html",
                "lkml",
                record,
                "reviewed_by_tag",
                "named in a Reviewed-by tag and as a maintainer in the kernel patch",
                at,
                "named reviewer",
                Obs(PERSONA, rev.group(1)),
                "lkml/2024/3/20/1008#reviewed-by",
            )
        )
    for n in (1289, 1350, 1475):
        who, _, rat = _lkml_fields(f"lkml_2024_3_29_{n}.html")
        events.append(
            Event(
                f"lkml_2024_3_29_{n}",
                f"lkml_2024_3_29_{n}.html",
                "lkml",
                record,
                "reply",
                "reply in the kernel patch thread",
                rat,
                ROLE_KERNEL,
                Obs(who),
                f"lkml/2024/3/29/{n}",
            )
        )
    return events


def parse_debian() -> list[Event]:
    record = "debian bug 1067708"
    t = _plain("debian_bug_1067708.html")
    t = re.sub(r"\n\s*\n+", "\n", t)
    maint = re.search(r"Maintainer for xz-utils is (.*?)(?:;|\n)", t)
    maint_tok = _tok(maint.group(1)) if maint else None
    reporter = re.search(r"Reported by: (.*)", t)
    rep_tok = _tok(reporter.group(1)) if reporter else None
    events = []
    # Header lines can wrap; match message blocks one at a time.
    for m in re.finditer(r"Message #(\d+) received at", t):
        block = t[m.start() : m.start() + 1500]
        n = int(m.group(1))
        frm = re.search(r"^From: (.*)$", block, re.M)
        dat = re.search(r"^Date: (.*)$", block, re.M)
        if not frm or not dat:
            continue
        tok = _tok(frm.group(1))
        name = _name_before_token(frm.group(1))
        is_report = tok is not None and tok == rep_tok and n == min_report(t, rep_tok)
        if tok is not None and tok == maint_tok:
            role = ROLE_DEB_MAINT
        elif re.search(r"^Control: ", block, re.M):
            role = "Debian bug triager"
        elif is_report:
            role = "bug reporter"
        else:
            role = "bug commenter"
        events.append(
            Event(
                "debian_bug_1067708",
                "debian_bug_1067708.html",
                "debian-bts",
                record,
                "bug_filed" if is_report else "reply",
                "bug filed asking Debian to update xz-utils to 5.6.1"
                if is_report
                else "reply on the Debian bug",
                _epoch(parsedate_to_datetime(dat.group(1))),
                role,
                Obs(name, tok),
                f"debian-bug-1067708/msg{n}",
                refs_records=_refs_in(t, record) if is_report else [],
            )
        )
    return events


def min_report(t: str, rep_tok: str | None) -> int:
    """Message number of the first message from the reporter (the bug-filing message)."""
    nums = []
    for m in re.finditer(r"Message #(\d+) received at", t):
        block = t[m.start() : m.start() + 600]
        frm = re.search(r"^From: (.*)$", block, re.M)
        if frm and _tok(frm.group(1)) == rep_tok:
            nums.append(int(m.group(1)))
    return min(nums) if nums else -1


def parse_launchpad() -> list[Event]:
    record = "launchpad bug 2059417"
    page = _plain("launchpad_bug_2059417.html")
    msgs = _json("lp_api_messages.json")["entries"]
    acts = _json("lp_api_activity.json")["entries"]
    # Display names from the page's "Name (handle)" pattern; only used in memory.
    names = {h: n.strip() for n, h in re.findall(r"([A-Z][\w.' -]{2,40}) \(([a-z0-9-]+)\)", page)}

    def who(link: str) -> Obs:
        h = link.rsplit("~", 1)[-1]
        return Obs(names.get(h), None, ("launchpad", h))

    events = []
    status_by = {
        a["person_link"].rsplit("~", 1)[-1]
        for a in acts
        if "status" in a["whatchanged"] and a["whatchanged"].startswith("xz-utils")
    }
    for i, m in enumerate(msgs):
        h = m["owner_link"].rsplit("~", 1)[-1]
        at = _iso_to_epoch(m["date_created"])
        if i == 0:
            events.append(
                Event(
                    "lp_api_messages",
                    "lp_api_messages.json",
                    "launchpad",
                    record,
                    "bug_filed",
                    "bug filed asking Ubuntu to sync xz-utils 5.6.1-1 from Debian",
                    at,
                    "bug reporter",
                    who(m["owner_link"]),
                    "launchpad-bug-2059417/msg0",
                    refs_records=_refs_in(page, record),
                )
            )
        else:
            events.append(
                Event(
                    "lp_api_messages",
                    "lp_api_messages.json",
                    "launchpad",
                    record,
                    "reply",
                    "comment on the Launchpad bug",
                    at,
                    ROLE_UBUNTU if h in status_by else "bug commenter",
                    who(m["owner_link"]),
                    f"launchpad-bug-2059417/msg{i}",
                )
            )
    for a in acts:
        if a["whatchanged"].startswith("xz-utils") and "status" in a["whatchanged"]:
            events.append(
                Event(
                    "lp_api_activity",
                    "lp_api_activity.json",
                    "launchpad",
                    record,
                    "status_change",
                    f"bug status changed: {a['oldvalue']} to {a['newvalue']}",
                    _iso_to_epoch(a["datechanged"]),
                    ROLE_UBUNTU,
                    who(a["person_link"]),
                    f"launchpad-bug-2059417/status/{a['datechanged']}",
                )
            )
    return events


def parse_xz_git() -> list[Event]:
    events = []
    upstream_names = {e.obs.name for e in parse_lkml() if e.role == ROLE_UPSTREAM}
    for f in sorted(RAW_DIR.glob("gh_xz_commit_*.json")):
        if f.name.endswith(".meta.json"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        sha = d["sha"]
        record = f"xz-git commit {sha[:8]}"
        a, c = d["commit"]["author"], d["commit"]["committer"]
        subject = d["commit"]["message"].splitlines()[0]
        at = _iso_to_epoch(c["date"])
        source_id = f.stem
        events.append(
            Event(
                source_id,
                f.name,
                "xz-git",
                record,
                "commit",
                f"commit authored for xz: {subject}",
                at,
                "contributor",
                Obs(a["name"], _tok(a["email"]), ("github", d["author"]["login"])),
                f"xz/commit/{sha[:8]}",
            )
        )
        committer_role = ROLE_UPSTREAM if c["name"] in upstream_names else "committer"
        events.append(
            Event(
                source_id,
                f.name,
                "xz-git",
                record,
                "commit_applied",
                f"commit applied to xz: {subject}",
                at,
                committer_role,
                Obs(c["name"], _tok(c["email"]), ("github", d["committer"]["login"])),
                f"xz/commit/{sha[:8]}#applied",
            )
        )
    return events


# ---------------------------------------------------------------- assembling
def all_events() -> tuple[list[Event], int]:
    """Every event up to the cutoff, in a fixed order, with stable ids. Also the number cut."""
    raw = parse_oss_fuzz() + parse_lkml() + parse_debian() + parse_launchpad() + parse_xz_git()
    raw.sort(key=lambda e: (e.at, e.source_id, e.kind, e.ref))
    keep = [e for e in raw if e.at <= _epoch(CUTOFF)]
    for i, e in enumerate(keep):
        e.index = i
        e.event_id = f"{e.source_id}:{e.kind}:{e.ref}"
    return keep, len(raw) - len(keep)


def build_registry(events: list[Event]) -> Registry:
    reg = Registry(load_salt())
    for e in events:
        reg.add(e.obs)
    reg.finish([e.obs for e in events])
    return reg


def source_urls() -> dict[str, str]:
    """source_id -> URL of the cached file it came from."""
    out = {}
    for e in all_events()[0]:
        out[e.source_id] = _meta_url(e.source_file)
    return out


def event_rows(events: list[Event], reg: Registry) -> list[dict]:
    rows = []
    for e in events:
        is_persona = PERSONA in reg.names.get(reg.find(reg.keys_of(e.obs)[0]), set())
        handle = None
        if is_persona and e.obs.handle:
            handle = e.obs.handle[1]
        rows.append(
            {
                "event_id": e.event_id,
                "source_id": e.source_id,
                "source_url": _meta_url(e.source_file),
                "place": e.place,
                "record": e.record,
                "at": _iso(e.at),
                "kind": e.kind,
                "action": e.action,
                "actor_role": e.role,
                "actor_hid": reg.hid(e.obs),
                "persona": PERSONA if is_persona else None,
                "public_handle": handle,
                "cites_records": e.refs_records,
            }
        )
    return rows


def main() -> None:
    events, cut = all_events()
    reg = build_registry(events)
    rows = event_rows(events, reg)
    out = {
        "cutoff": CUTOFF.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "events_after_cutoff_not_included": cut,
        "role_evidence": ROLE_EVIDENCE,
        "events": rows,
    }
    path = Path(__file__).resolve().parents[3] / "eval" / "results" / "ecosystem_events.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[r["place"]] = kinds.get(r["place"], 0) + 1
    print(len(rows), "events", kinds, "cut", cut)


if __name__ == "__main__":
    main()
