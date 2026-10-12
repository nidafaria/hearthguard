"""Wording rules for every note and Show me why text. Used by the renderer and by the tests.

Spec §4.4: Hearthguard never labels anyone an attacker. §12.2: the note is a question, never an
accusation. These rules are a backstop: they catch the phrasings we know about, and the tests
check the rendered output against them.
"""

import re

ACCUSATION_PATTERNS = [
    r"\battackers?\b",
    r"\bis compromised\b",
    r"\bimpostor\b",
    r"\bthreat actor\b",
    r"\bmalicious (?:actor|user|account|maintainer|person)\b",
    r"\b(?:is|are|was|were) (?:a |an |the )?(?:thief|liar|criminal|guilty|culprit|traitor)\b",
    r"\b(?:he|she|they|you) (?:did|stole|sabotaged|planted|lied|hacked)\b",
    r"\byou (?:are|were) (?:the )?(?:attacker|culprit|guilty)\b",
    r"\b(?:he|she|they) (?:is|are) (?:the )?(?:attacker|culprit|guilty)\b",
]
_ACCUSATION_RE = [re.compile(p, re.IGNORECASE) for p in ACCUSATION_PATTERNS]


def find_accusations(text: str) -> list[str]:
    """Every accusing phrase found in the text. An empty list means the text passes."""
    return [m.group(0) for rx in _ACCUSATION_RE for m in rx.finditer(text)]


def ends_with_question(note: str) -> bool:
    """The note asks the person in charge something: one of its lines ends with a question mark."""
    return any(line.rstrip().endswith("?") for line in note.splitlines())
