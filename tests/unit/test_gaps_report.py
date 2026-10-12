"""`make gaps CASE=xz` and the gaps and summary sections of `make demo`.

They read saved files, say NOT COMPUTED when a file is missing, and print roles, never names."""

import json

from eval import demo, gaps_report


def fixture_doc() -> dict:
    return {
        "graph": "ecosystem_xz",
        "scope": "Signals come from the cached records only.",
        "reading_the_labels": "UNREACHABLE: absence of evidence.",
        "decisions_computed": 2,
        "decisions_not_computed": 0,
        "gap_rows": 1,
        "unreachable_rows": 1,
        "unnoticed_rows": 0,
        "label_confidence_counts": {"absence-of-evidence": 1},
        "decisions": [
            {
                "decision": "debian-upgrade-request-bug1",
                "place": "debian-bts",
                "deciding_role": "Debian package maintainer",
                "status": "COMPUTED",
                "reason": None,
                "gaps": [
                    {
                        "gap": "UNREACHABLE",
                        "signal_kind": "pr_opened",
                        "signal_place": "xz-git",
                        "signal_at": "2024-03-01T00:00:00Z",
                        "label_confidence": "absence-of-evidence",
                    }
                ],
            },
            {
                "decision": "lkml-entry",
                "place": "lkml",
                "deciding_role": "Linux kernel reviewer",
                "status": "NOT COMPUTED",
                "reason": "no role watches lkml",
                "gaps": [],
            },
        ],
    }


def test_gaps_markdown_lists_roles_and_labels_and_not_computed_rows():
    text = gaps_report.markdown(fixture_doc())
    assert (
        "| debian-upgrade-request-bug1 | debian-bts | Debian package maintainer | COMPUTED | "
        "UNREACHABLE" in text
    )
    assert (
        "| lkml-entry | lkml | Linux kernel reviewer | NOT COMPUTED | no role watches lkml" in text
    )
    assert "1 UNREACHABLE, 0 UNNOTICED" in text


def test_gaps_main_writes_the_markdown_from_the_saved_file(tmp_path, monkeypatch, capsys):
    (tmp_path / "ecosystem_gaps.json").write_text(json.dumps(fixture_doc()), encoding="utf-8")
    monkeypatch.setattr(gaps_report, "RESULTS", tmp_path)
    assert gaps_report.main(["xz"]) == 0
    assert (
        (tmp_path / "gaps_xz.md")
        .read_text(encoding="utf-8")
        .startswith("# Visibility gaps, ecosystem_xz")
    )
    assert "Debian package maintainer" in capsys.readouterr().out


def test_gaps_main_says_what_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gaps_report, "RESULTS", tmp_path)
    assert gaps_report.main(["xz"]) == 1
    assert "run `make ecosystem-xz` first" in capsys.readouterr().out


def test_gaps_main_refuses_an_unknown_case(capsys):
    assert gaps_report.main(["census"]) == 2
    assert "no gaps for CASE=census" in capsys.readouterr().out


def test_demo_gaps_section_is_not_computed_when_the_file_is_missing(tmp_path):
    text = demo.gaps_section(tmp_path)
    assert text.startswith("NOT COMPUTED: ecosystem_gaps.json not found")


def test_demo_hardening_section_is_not_computed_when_both_files_are_missing(tmp_path):
    text = demo.hardening_section(tmp_path)
    assert "NOT COMPUTED: xz_hardening.json not found" in text
    assert "NOT COMPUTED: hardening_fixture.json not found" in text


def test_demo_tallowdate_section_is_labelled_synthetic_and_never_invents_cost(tmp_path):
    text = demo.tallowdate_section(tmp_path)
    assert demo.SYNTHETIC in text
    assert "NOT COMPUTED: tallowdate_decision.json not found" in text


def test_demo_tallowdate_section_copies_the_cost_status_from_the_file(tmp_path):
    (tmp_path / "tallowdate_decision.json").write_text(
        json.dumps(
            {"quarters": [{"quarter": "2023-Q1", "decision": "HOLD", "hold_reason": "unknown"}]}
        ),
        encoding="utf-8",
    )
    (tmp_path / "tallowdate_detector_status.json").write_text(
        json.dumps(
            {
                "quarters": [
                    {
                        "quarter": "2023-Q1",
                        "checks": {
                            "takeover_cost": {"status": "NOT COMPUTED", "value": None},
                            "guardians": {"status": "COMPUTED", "value": 2},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    text = demo.tallowdate_section(tmp_path)
    assert "| 2023-Q1 | NOT COMPUTED | 2 |" in text


def test_demo_prints_the_replay_table_before_the_new_sections(capsys):
    assert demo.main() == 0
    out = capsys.readouterr().out
    assert out.index("| quarter |") < out.index("## Visibility gaps, xz")
    assert out.index("## Visibility gaps, xz") < out.index("## Hardening, from saved results")
    assert out.index("## Hardening, from saved results") < out.index(
        "## tallowdate, synthetic case"
    )
