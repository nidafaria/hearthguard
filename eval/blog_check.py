"""Checks docs/blog/post.md before it is published. Exit 1 on any failure.

Rules (docs/blog/ and the agent D brief):
- Every paragraph with a number (digits or a number word) names a source file in the same paragraph.
  A paragraph is a block between blank lines; headings count as paragraphs.
- Every source file named in the post exists in the repo. Paths under data/raw/ are
  git-ignored and exist only in the main checkout, so they are not required to exist here.
- No banned word: wins, solves, proves, perfect, guaranteed.
- Word count (whitespace-separated tokens in the whole file) is 1,200 to 1,600.
- A paragraph that mentions the synthetic story (tallowdate, "synthetic story", "Act II")
  also contains the word "synthetic".

Stdlib only. Run with: make blog-check   (or .\\make.ps1 blog-check on Windows).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POST = ROOT / "docs" / "blog" / "post.md"

WORD_MIN, WORD_MAX = 1200, 1600
BANNED = re.compile(r"\b(wins|solves|proves|perfect|guaranteed)\b", re.IGNORECASE)
SOURCE = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:json|md|py|html|csv|yaml|sha256|txt)\b")
NUMBER_WORDS = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|"
    r"sixty|seventy|eighty|ninety|hundred|thousand|million)\b",
    re.IGNORECASE,
)
SYNTHETIC_STORY = re.compile(r"tallowdate|synthetic story|\bAct II\b", re.IGNORECASE)


def paragraphs(text):
    return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]


def strip_sources(block):
    return SOURCE.sub(" ", block)


def main():
    if not POST.exists():
        print(f"FAIL: {POST.relative_to(ROOT)} does not exist")
        return 1

    text = POST.read_text(encoding="utf-8")
    failures = []

    words = len(text.split())
    if not (WORD_MIN <= words <= WORD_MAX):
        failures.append(f"word count {words} is outside {WORD_MIN}-{WORD_MAX}")

    total_numbers = 0
    sourced_numbers = 0
    for i, block in enumerate(paragraphs(text), start=1):
        prose = strip_sources(block)
        numbers = len(re.findall(r"\d[\d,.]*", prose)) + len(NUMBER_WORDS.findall(prose))
        has_source = bool(SOURCE.search(block))
        if numbers:
            total_numbers += numbers
            if has_source:
                sourced_numbers += numbers
            else:
                preview = block.splitlines()[0][:70]
                failures.append(
                    f"paragraph {i} has {numbers} number(s) and no source file: {preview!r}"
                )

        for hit in BANNED.findall(block):
            failures.append(f"paragraph {i} uses banned word {hit!r}")

        if SYNTHETIC_STORY.search(block) and not re.search(r"\bsynthetic\b", block, re.IGNORECASE):
            failures.append(
                f"paragraph {i} mentions the synthetic story without the word 'synthetic'"
            )

    missing = []
    for src in sorted(set(SOURCE.findall(text))):
        if src.startswith("data/raw/"):
            continue
        if not (ROOT / src).exists():
            missing.append(src)
    for src in missing:
        failures.append(f"source file named in the post does not exist: {src}")

    print(f"word count: {words} (allowed {WORD_MIN}-{WORD_MAX})")
    print(
        f"numbers in post: {total_numbers}; with a source in the same paragraph: {sourced_numbers}"
    )
    print(f"source files named: {len(set(SOURCE.findall(text)))}; missing in repo: {len(missing)}")

    if failures:
        print("blog-check: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("blog-check: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
