"""Checks the demo video package against the files it cites.

Reads docs/video/shot_list.md and docs/video/narration.md, then:
- finds every quote word for word in data/raw/mail/xz-devel/*.html (case and punctuation exact)
- reads every number from its eval/results/*.json file (NOT COMPUTED if the file says so)
- checks the timing (contiguous scenes, at most 3:00, total line matches)
- checks every Act II scene carries a SYNTHETIC label on screen
- checks every digit shown on screen or spoken is a declared, sourced number
- checks narration.md says the same as the shot list

Writes eval/results/video_quotes.json and eval/results/video_numbers.json, then exits 1 on any failure.

  uv run python -m eval.video_check                 # the real package
  uv run python -m eval.video_check --self-test     # broken fixtures must fail, a good one must pass
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIL_DIR = ROOT / "data" / "raw" / "mail" / "xz-devel"
RESULTS = ROOT / "eval" / "results"
VIDEO_DIR = ROOT / "docs" / "video"
MAX_SECONDS = 180

SCENE_RE = re.compile(r"^## (S\d+) · (\d+:\d{2})[–-](\d+:\d{2}) · (.+)$")
FIELD_RE = re.compile(r"^- \*\*([^:*]+):\*\* ?(.*)$")
TOTAL_RE = re.compile(r"^\*\*Total:\*\* (\d+:\d{2})\b")
QUOTE_RE = re.compile(r'^(Q\d+) · (msg\d+\.html) — "(.*)"$')
NUMBER_RE = re.compile(r"^([A-Z0-9_]+) = (.+)$")
NARR_RE = re.compile(r"^\*\*(S\d+):\*\* (.+)$")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DIGITS_RE = re.compile(r"\d[\d,]*\d|\d")
PATH_RE = re.compile(r"(?:data|eval|docs)/[\w./-]+")

# Every number the video may show. Each one names the saved file and field it comes from.
# kind "json": read from a file. kind "quote": the message date of a quote in video_quotes.json.
# A json number whose field says NOT COMPUTED is recorded as NOT COMPUTED and cannot be shown.
NUMBERS = [
    {"id": "TAKEOVER_COST_XZ", "label": "Takeover cost, xz (requested: 1)", "kind": "json",
     "file": "eval/results/xz_takeover_status.json", "field": "takeover_cost.value",
     "status_field": "takeover_cost.status", "fmt": "int"},
    {"id": "SIX_PUBLIC_PLACES", "label": "Public places with traces (requested: 6)", "kind": "none",
     "note": "No saved result. eval/results/completion_full.md lists the ecosystem records as NOT STARTED."},
    {"id": "ACTIONS", "label": "Actions in the xz git graph", "kind": "json",
     "file": "eval/results/xz_ingest.json", "field": "counts_after_run_1.nodes.Action", "fmt": "int"},
    {"id": "ACTORS", "label": "Actors in the xz git graph", "kind": "json",
     "file": "eval/results/xz_ingest.json", "field": "counts_after_run_1.nodes.Actor", "fmt": "int"},
    {"id": "TESTS_PASSED", "label": "Tests passed, latest make.ps1 test run", "kind": "json",
     "file": "eval/results/final_tests.json", "field": "passed", "fmt": "int"},
    {"id": "READER_DONE", "label": "Reader messages done", "kind": "json",
     "file": "eval/results/reader_full_progress.json", "field": "done", "fmt": "int"},
    {"id": "READER_TOTAL", "label": "Reader messages in scope", "kind": "json",
     "file": "eval/results/reader_full_progress.json", "field": "total", "fmt": "int"},
    {"id": "READER_TOO_LONG", "label": "Reader messages too long to read", "kind": "json",
     "file": "eval/results/reader_full_run.json", "field": "totals.messages_not_read_too_long", "fmt": "int"},
    {"id": "ACCOUNT_A", "label": "Synthetic account A created", "kind": "json",
     "file": "eval/results/tallowdate_demo_script.json", "field": "beats.1.reads.created_a.value", "fmt": "text"},
    {"id": "ACCOUNT_B", "label": "Synthetic account B created", "kind": "json",
     "file": "eval/results/tallowdate_demo_script.json", "field": "beats.1.reads.created_b.value", "fmt": "text"},
    {"id": "ACCOUNT_C", "label": "Synthetic account C created", "kind": "json",
     "file": "eval/results/tallowdate_demo_script.json", "field": "beats.1.reads.created_c.value", "fmt": "text"},
    {"id": "TOMAS_REVIEWS", "label": "Synthetic reviewer's reviews", "kind": "json",
     "file": "eval/results/tallowdate_load.json", "field": "facts.tomas_review_count.value", "fmt": "int"},
    {"id": "DATE_Q1", "label": "Message date, quote Q1", "kind": "quote", "quote": "Q1", "fmt": "month_year"},
    {"id": "DATE_Q2", "label": "Message date, quote Q2", "kind": "quote", "quote": "Q2", "fmt": "month_year"},
    {"id": "DATE_Q3", "label": "Message date, quote Q3", "kind": "quote", "quote": "Q3", "fmt": "day_month_year"},
]
NUMBER_BY_ID = {n["id"]: n for n in NUMBERS}

REQUIRED_NUMBERS = ["TAKEOVER_COST_XZ", "SIX_PUBLIC_PLACES", "ACTIONS", "ACTORS", "TESTS_PASSED", "READER_DONE"]


def ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def to_seconds(mmss: str) -> int:
    minutes, seconds = mmss.split(":")
    return int(minutes) * 60 + int(seconds)


def to_mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def dotted(data, path: str):
    """Walk a dotted path through dicts and lists. Raises KeyError if a part is missing."""
    node = data
    for part in path.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return node


def fmt_value(value, fmt: str) -> str:
    if fmt == "int":
        return f"{int(value):,}"
    if fmt == "month_year":
        return f"{datetime.fromisoformat(value.replace('Z', '+00:00')):%B %Y}"
    if fmt == "day_month_year":
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return f"{d.day} {d:%B %Y}"
    return str(value)


def load_mail():
    index = json.loads((MAIL_DIR / "index.json").read_text(encoding="utf-8"))
    dates = {m["file"]: m.get("date_utc") for m in index["messages"]}
    texts = {}
    for path in sorted(MAIL_DIR.glob("msg*.html")):
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        lines = text.splitlines()
        full = ws(" ".join(lines))
        # Lines starting with ">" are the reply quoting an earlier message, not the author's own words.
        original = ws(" ".join(line for line in lines if not line.lstrip().startswith(">")))
        texts[path.name] = (original, full)
    return dates, texts


def parse_shot_list(path: Path):
    """Return (scenes, total_line). Each scene holds its header numbers and its fields as lists."""
    scenes, total_line, current = [], None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        total = TOTAL_RE.match(line)
        if total:
            total_line = total[1]
            continue
        header = SCENE_RE.match(line)
        if header:
            current = {"id": header[1], "start": to_seconds(header[2]), "end": to_seconds(header[3]),
                       "act": header[4], "fields": {}}
            scenes.append(current)
            continue
        if line.startswith("## "):
            current = None  # a section that is not a scene, such as the cut list
            continue
        field = FIELD_RE.match(line)
        if current is not None and field:
            current["fields"].setdefault(field[1].strip(), []).append(field[2].strip())
    return scenes, total_line


def check_quote(text: str, cited_name: str, dates, texts):
    exact_orig = sorted(f for f, (orig, _) in texts.items() if text in orig)
    exact_any = sorted(f for f, (_, full) in texts.items() if text in full)
    ci_hits = sorted(f for f, (_, full) in texts.items() if text.lower() in full.lower())
    found = bool(exact_any)
    cited_path = f"data/raw/mail/xz-devel/{cited_name}"
    record = {
        "text": text,
        "status": "FOUND" if found else "NOT FOUND",
        "cited_file": cited_path,
        "file": None,
        "message_date_utc": dates.get(cited_name),
        "also_found_in": [],
        "case_insensitive_match_in": [] if found else [f"data/raw/mail/xz-devel/{f}" for f in ci_hits],
    }
    if found:
        primary = cited_name if cited_name in exact_any else exact_any[0]
        record["file"] = f"data/raw/mail/xz-devel/{primary}"
        record["only_in_quoted_reply"] = primary not in exact_orig
        record["also_found_in"] = [f"data/raw/mail/xz-devel/{f}" for f in exact_any if f != primary]
    return record


def write_results(quotes: dict, numbers: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "video_quotes.json").write_text(json.dumps(
        {"matching": "exact: case-sensitive, punctuation-exact, whitespace-normalised, HTML unescaped",
         "corpus": "data/raw/mail/xz-devel/*.html", "quotes": quotes}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (RESULTS / "video_numbers.json").write_text(json.dumps(
        {"rule": "every number on screen or in narration must have status COMPUTED and a source file",
         "numbers": list(numbers.values())}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(shot_list: Path, write: bool) -> dict:
    """Run every check. Returns {"failures": [...], "quotes": {...}, "numbers": {...}, "summary": {...}}."""
    failures: list[str] = []
    narration_path = shot_list.with_name("narration.md")
    scenes, total_line = parse_shot_list(shot_list)
    dates, texts = load_mail()

    # 1. Quotes: every quote in the shot list, found word for word in the cached mail.
    quotes: dict[str, dict] = {}
    for scene in scenes:
        for value in scene["fields"].get("Quote", []):
            m = QUOTE_RE.match(value)
            if not m:
                failures.append(f"{scene['id']}: quote line is not in the form Q1 · msgNNNNN.html — \"text\"")
                continue
            qid, cited_name, text = m[1], m[2], m[3]
            if qid in quotes:
                failures.append(f"{qid}: declared twice")
                continue
            quotes[qid] = check_quote(text, cited_name, dates, texts)
            if quotes[qid]["status"] == "NOT FOUND":
                failures.append(f"{qid} NOT FOUND word for word in data/raw/mail/xz-devel/*.html: \"{text}\"")
            elif quotes[qid]["file"] != quotes[qid]["cited_file"]:
                failures.append(f"{qid} is found in {quotes[qid]['file']}, not the cited {quotes[qid]['cited_file']}")

    # 2. Numbers: read each one from its file. Record every candidate, shown or not.
    numbers: dict[str, dict] = {}
    for spec in NUMBERS:
        rec = {"id": spec["id"], "label": spec["label"], "source_file": None, "source_field": None,
               "value": None, "display": None, "status": "NOT COMPUTED", "used_in_scenes": []}
        if spec["kind"] == "json":
            rec["source_file"], rec["source_field"] = spec["file"], spec["field"]
            source = json.loads((ROOT / spec["file"]).read_text(encoding="utf-8"))
            if spec.get("status_field") and dotted(source, spec["status_field"]) == "NOT COMPUTED":
                rec["reason"] = f"{spec['file']} field {spec['status_field']} is NOT COMPUTED"
            else:
                value = dotted(source, spec["field"])
                if value is not None:
                    rec.update(value=value, display=fmt_value(value, spec["fmt"]), status="COMPUTED")
        elif spec["kind"] == "quote":
            q = quotes.get(spec["quote"])
            rec["source_file"] = "eval/results/video_quotes.json"
            rec["source_field"] = f"quotes.{spec['quote']}.message_date_utc"
            if q and q["message_date_utc"]:
                rec.update(value=q["message_date_utc"], display=fmt_value(q["message_date_utc"], spec["fmt"]),
                           status="COMPUTED")
        else:
            rec["reason"] = spec["note"]
        numbers[spec["id"]] = rec

    # Write the results before the scene checks, so a Source line can cite them. Rewritten after the scenes.
    if write:
        write_results(quotes, numbers)

    # 3. Scenes: timing, labels, sources, and every digit shown.
    if not scenes:
        failures.append("no scenes found in the shot list")
    expected_start = 0
    total = 0
    for scene in scenes:
        sid, fields = scene["id"], scene["fields"]
        if scene["start"] != expected_start:
            failures.append(f"{sid}: starts at {to_mmss(scene['start'])}, expected {to_mmss(expected_start)}")
        if scene["end"] <= scene["start"]:
            failures.append(f"{sid}: ends at or before it starts")
        expected_start = scene["end"]
        total = scene["end"]

        shown_text = " ".join(fields.get("Screen", []) + fields.get("On screen", []) + fields.get("Narration", []))
        source_text = " ".join(fields.get("Source", []))
        allowed_displays = []

        # Quotes shown in this scene must cite a file the check found them in.
        for value in fields.get("Quote", []):
            m = QUOTE_RE.match(value)
            if m and m[1] in quotes:
                if m[2] not in source_text:
                    failures.append(f"{sid}: Source does not name {m[2]} for quote {m[1]}")

        # Numbers: declared, sourced, not NOT COMPUTED, and shown exactly as the file gives them.
        for value in fields.get("Number", []):
            m = NUMBER_RE.match(value)
            if not m or m[1] not in numbers:
                failures.append(f"{sid}: number line '{value}' names no known number id")
                continue
            rec = numbers[m[1]]
            rec["used_in_scenes"].append(sid)
            if rec["status"] != "COMPUTED":
                failures.append(f"{sid}: number {m[1]} is NOT COMPUTED ({rec.get('reason', 'no source')}); remove it from the scene")
                continue
            if m[2].strip() != rec["display"]:
                failures.append(f"{sid}: number {m[1]} is shown as '{m[2].strip()}' but the file gives '{rec['display']}'")
            if rec["source_file"] not in source_text:
                failures.append(f"{sid}: Source does not name {rec['source_file']} for number {m[1]}")
            allowed_displays.append(rec["display"])

        # Every digit on screen or spoken must sit inside a declared number's shown text.
        for token in DIGITS_RE.findall(TIME_RE.sub(" ", shown_text)):
            if not any(token in display for display in allowed_displays):
                failures.append(f"{sid}: digit '{token}' is on screen or spoken with no declared, sourced number")

        # Every path cited in Source must exist.
        for cited in PATH_RE.findall(source_text):
            if not (ROOT / cited.rstrip(".,;)")).exists():
                failures.append(f"{sid}: Source cites {cited}, which does not exist")

        # Act II is synthetic and must say so on screen.
        if "Act II" in scene["act"] and not any("SYNTHETIC" in s for s in fields.get("On screen", [])):
            failures.append(f"{sid}: Act II scene has no SYNTHETIC label on screen")

    # 4. Timing: the total must be at most 3:00 and match the Total line.
    if total > MAX_SECONDS:
        failures.append(f"total video time {to_mmss(total)} is over {to_mmss(MAX_SECONDS)}")
    if total_line is None:
        failures.append("the shot list has no '**Total:** m:ss' line")
    elif to_seconds(total_line) != total:
        failures.append(f"Total line says {total_line} but the scenes add up to {to_mmss(total)}")

    # 5. Narration: narration.md must hold the same line as each scene.
    narr = {}
    if narration_path.exists():
        for line in narration_path.read_text(encoding="utf-8").splitlines():
            m = NARR_RE.match(line)
            if m:
                narr[m[1]] = m[2]
    for scene in scenes:
        want = " ".join(scene["fields"].get("Narration", []))
        if scene["id"] not in narr:
            failures.append(f"{scene['id']}: no narration line in narration.md")
        elif narr[scene["id"]] != want:
            failures.append(f"{scene['id']}: narration.md differs from the shot list")

    used = [n for n in numbers.values() if n["used_in_scenes"]]
    summary = {
        "total": to_mmss(total),
        "quotes_found": sum(q["status"] == "FOUND" for q in quotes.values()),
        "quotes_not_found": sum(q["status"] == "NOT FOUND" for q in quotes.values()),
        "numbers_with_source": sum(n["status"] == "COMPUTED" for n in used),
        "numbers_not_computed": sum(n["status"] != "COMPUTED" for n in used),
        "numbers_required_status": {k: numbers[k]["status"] for k in REQUIRED_NUMBERS},
    }

    if write:
        write_results(quotes, numbers)

    return {"failures": failures, "quotes": quotes, "numbers": numbers, "summary": summary}


def print_report(result: dict) -> None:
    s = result["summary"]
    for failure in result["failures"]:
        print(f"FAIL  {failure}")
    print()
    print(f"quotes: {s['quotes_found']} found, {s['quotes_not_found']} NOT FOUND")
    print(f"numbers used in the shot list: {s['numbers_with_source']} with a source, "
          f"{s['numbers_not_computed']} NOT COMPUTED")
    for key, status in s["numbers_required_status"].items():
        print(f"  {key}: {status}")
    print(f"total video time: {s['total']} (limit 3:00)")
    verdict = "PASS" if not result["failures"] else f"FAIL ({len(result['failures'])} problems)"
    print(f"video-check: {verdict}")


def self_test() -> int:
    # Fixtures cite eval/results/*.json, so write the real results first, as the real run does.
    run(VIDEO_DIR / "shot_list.md", write=True)
    good_scene = (
        "## S1 · 0:00–0:10 · Act I (real)\n"
        "- **Screen:** Post\n"
        "- **On screen:** xz-devel · June 2022\n"
        "- **Narration:** The project was an unpaid hobby project.\n"
        "- **Quote:** Q2 · msg00567.html — \"unpaid hobby project\"\n"
        "- **Number:** DATE_Q2 = June 2022\n"
        "- **Source:** data/raw/mail/xz-devel/msg00567.html; eval/results/video_quotes.json\n"
    )
    good_narr = "**S1:** The project was an unpaid hobby project.\n"
    cases = {
        "good fixture passes": (good_scene + "\n**Total:** 0:10\n", good_narr, True),
        "wrong quote fails": (good_scene.replace("hobby project\"", "hobby projects\"") + "\n**Total:** 0:10\n",
                              good_narr, False),
        "over 3:00 fails": (good_scene.replace("0:00–0:10", "0:00–3:01") + "\n**Total:** 3:01\n",
                            good_narr, False),
        "Act II without SYNTHETIC fails": (good_scene.replace("Act I (real)", "Act II (synthetic)")
                                           + "\n**Total:** 0:10\n", good_narr, False),
        "NOT COMPUTED number fails": (good_scene.replace("DATE_Q2 = June 2022", "TAKEOVER_COST_XZ = 1")
                                      + "\n**Total:** 0:10\n", good_narr, False),
        "undeclared digit fails": (good_scene.replace("The project was an unpaid hobby project.",
                                                      "The project had 94 messages.") + "\n**Total:** 0:10\n",
                                   "**S1:** The project had 94 messages.\n", False),
        "missing source fails": (good_scene.replace("; eval/results/video_quotes.json", "")
                                 + "\n**Total:** 0:10\n", good_narr, False),
    }
    passed = failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for index, (name, (shot, narr, expect_pass)) in enumerate(cases.items()):
            folder = Path(tmp) / f"case{index}"
            folder.mkdir()
            (folder / "shot_list.md").write_text(shot, encoding="utf-8")
            (folder / "narration.md").write_text(narr, encoding="utf-8")
            result = run(folder / "shot_list.md", write=False)
            ok = (not result["failures"]) == expect_pass
            passed += ok
            failed += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name} ({len(result['failures'])} problems)")

    # The real package: it must fail only on the quotes that are not word for word in the mail.
    real = run(VIDEO_DIR / "shot_list.md", write=False)
    only_quotes = bool(real["failures"]) and all("NOT FOUND" in f for f in real["failures"])
    passed += only_quotes
    failed += not only_quotes
    print(f"{'PASS' if only_quotes else 'FAIL'}  real package fails only on NOT FOUND quotes "
          f"({len(real['failures'])} problems)")
    print(f"self-test: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--shot-list", type=Path, default=VIDEO_DIR / "shot_list.md")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    result = run(args.shot_list, write=args.shot_list == VIDEO_DIR / "shot_list.md")
    print_report(result)
    return 0 if not result["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
