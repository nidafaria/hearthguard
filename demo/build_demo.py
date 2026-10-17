"""Builds demo/index.html: one self-contained page that shows every Hearthguard screen.

The page carries the saved result files themselves, verbatim, inside
<script type="application/json" data-file="..."> blocks, and parses them when it loads. No number
is computed here. Two exceptions, both labelled on the page:

- ecosystem_events.json: the persona, public handle, hashed actor id and source URL fields are
  removed. The UI never reads them (roles, not names).
- rendered/inbox_notes.json: the note, headline, "why" and digest text for each quarter, rendered
  from the saved decision files by the same pure functions the local API uses
  (core/agents/liaison.py, core/agents/digest.py, slack_app/show_why.py).

Fonts (SIL OFL, see demo/fonts/) are embedded as base64 so the page works offline.

Run: uv run python -m demo.build_demo
"""

import base64
import json
import subprocess
from pathlib import Path

from core.agents import digest, investigator, liaison
from core.agents.cases import CASES, normalize_rows
from slack_app.show_why import render_show_why

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
DEMO = Path(__file__).resolve().parent
TEMPLATE = DEMO / "template.html"
OUT = DEMO / "index.html"
DOCS_OUT = ROOT / "docs" / "index.html"

FILES = [
    "xz_replay.json",
    "pressure_vouch_status.json",
    "xz_quarterly_status.json",
    "decision_status.json",
    "xz_grant_search.json",
    "xz_takeover_status.json",
    "tallowdate_detector_status.json",
    "tallowdate_decision.json",
    "trust_map_tallowdate.json",
    "ecosystem_gaps.json",
    "xz_hardening.json",
    "hardening_fixture.json",
    "hardening_redteam_xz.json",
    "hardening_redteam_tallowdate.json",
    "ablation_memory.json",
    "connect_repo_run.json",
    "learning_verify.json",
    "video_quotes.json",
    "slack_preview.json",
]
EVENT_FIELDS_DROPPED = ("persona", "public_handle", "actor_hid", "source_url", "source_id")
FONTS = {
    "fontDisplay": "instrument-serif-400.woff2",
    "fontDisplayItalic": "instrument-serif-400-italic.woff2",
    "fontText": "geist-var.woff2",
    "fontMono": "geist-mono-var.woff2",
}


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def events() -> dict:
    doc = load("ecosystem_events.json")
    doc["events"] = [
        {k: v for k, v in e.items() if k not in EVENT_FIELDS_DROPPED} for e in doc["events"]
    ]
    doc["fields_removed_at_build"] = list(EVENT_FIELDS_DROPPED)
    return doc


def tallow_why(row: dict) -> str:
    det = {q["quarter"]: q for q in load("tallowdate_detector_status.json")["quarters"]}
    checks = det[row["quarter"]]["checks"]
    lines = [
        f"Show me why: {row['quarter']}, decision {row['decision']}",
        f"Why held: {row.get('hold_reason') or 'not recorded'}.",
        "",
    ]
    names = [("pressure", "Pressure"), ("vouch", "Vouch"), ("rush", "Rush")]
    names += [("bypass", "Bypass"), ("lone_keeper", "Lone keeper")]
    for i, (k, label) in enumerate(names, 1):
        c = checks.get(k) or {}
        lines.append(f"{i}. {label}: {c.get('status', 'NOT COMPUTED')}")
        lines.append(f"   Reason: {c.get('reason') or 'no reason saved'}")
        lines.append("   File: tallowdate_detector_status.json")
        for q in c.get("queries") or []:
            lines.append(f"   Query {q['name']} ({q.get('rows')} rows, {q.get('ms', 0):.1f} ms):")
            lines.append(f"     {q['query']}")
    lines += ["", "Saved results only; nothing was re-run."]
    return "\n".join(lines)


def inbox_notes() -> dict:
    preview = {q["quarter"]: q for q in load("slack_preview.json")["quarters"]}
    out: dict = {
        "rendered_by": "core/agents/liaison.py, core/agents/digest.py, slack_app/show_why.py",
        "controls": list(liaison.CONTROLS),
        "suggested_questions": list(investigator.SUPPORTED),
        "draft_boundary_reply": liaison.draft_text("boundary_reply"),
        "cases": {},
    }
    for cid, case in CASES.items():
        notes = []
        for r in normalize_rows(case, RESULTS):
            if cid == "xz":
                why = preview.get(r["quarter"], {}).get("show_why") or render_show_why(r, RESULTS)
            else:
                why = tallow_why(r)
            notes.append(
                {
                    "quarter": r["quarter"],
                    "decision": r["decision"],
                    "headline": liaison.headline(case, r),
                    "note": liaison.note_text(case, r),
                    "why": why,
                }
            )
        out["cases"][cid] = {
            "label": case.label,
            "synthetic": case.synthetic,
            "decision_file": case.decision_file,
            "notes": notes,
            "digest": digest.build_digest(case, RESULTS),
        }
    return out


def block(name: str, doc: dict) -> str:
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" data-file="{name}">{text}</script>'


def main() -> None:
    blocks = [block(n, load(n)) for n in FILES]
    blocks.append(block("ecosystem_events.json", events()))
    blocks.append(block("rendered/inbox_notes.json", inbox_notes()))
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    html = TEMPLATE.read_text(encoding="utf-8")
    for token, fname in FONTS.items():
        b64 = base64.b64encode((DEMO / "fonts" / fname).read_bytes()).decode("ascii")
        html = html.replace(f"__{token}__", b64)
    html = html.replace("<!--__FILES__-->", "\n".join(blocks))
    html = html.replace("__COMMIT__", head)
    OUT.write_text(html, encoding="utf-8")
    DOCS_OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(html) // 1024} KB, {len(blocks)} files)")
    print(f"wrote {DOCS_OUT.relative_to(ROOT)} ({len(html) // 1024} KB, {len(blocks)} files)")


if __name__ == "__main__":
    main()
