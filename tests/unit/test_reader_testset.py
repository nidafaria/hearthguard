"""The test-set rule: deterministic, stratified by year, honest about a year that is too small."""

import csv
import json

import pytest

from eval import reader_freeze as rf
from eval import reader_sheet as sheet
from eval import reader_spotcheck as rs
from eval import reader_testset as rt
from packs.oss import mail_cache

needs_cache = pytest.mark.skipif(
    not (mail_cache.RAW_ROOT / "index.json").exists() or not rs.SAMPLE_PATH.exists(),
    reason="mail cache or spot-check sample absent",
)


def rows_for(pools: dict[str, int], first_id: int = 1000, status: int = 200) -> list[dict]:
    rows, n = [], first_id
    for year, count in pools.items():
        for i in range(count):
            rows.append(
                {"msg": n, "status": status, "date_utc": f"{year}-06-{1 + i % 28:02d}T12:00:00Z"}
            )
            n += 1
    return rows


POOLS = {"2021": 40, "2022": 31, "2023": 8, "2024": 20}


# ------------------------------------------------------------------ the pools
def test_pools_keep_only_found_messages_in_the_window_and_not_excluded():
    rows = rows_for({"2021": 3})
    rows += [
        {
            "msg": 1,
            "status": 200,
            "date_utc": "2020-12-31T23:59:59Z",
        },  # one second before the window
        {"msg": 2, "status": 200, "date_utc": "2025-01-01T00:00:00Z"},  # after it
        {"msg": 3, "status": 404, "date_utc": "2022-01-01T00:00:00Z"},  # no page
        {"msg": 4, "status": 200, "date_utc": None},  # no date
        {"msg": 5, "status": 200, "date_utc": "2024-12-31T23:59:59Z"},  # last second of the window
    ]
    pools = rt.year_pools(rows, exclude={1000})
    assert pools["2021"] == [1001, 1002] and pools["2024"] == [5]
    assert pools["2022"] == [] and pools["2023"] == []


# ------------------------------------------------------------------ every k-th message
def test_every_kth_starts_at_the_first_id_and_takes_fifteen():
    ids = list(range(1, 123))  # 122 messages: k = floor(122 / 15) = 8
    picked, k = rt.pick_every_kth(ids, 15)
    assert k == 8 and len(picked) == 15
    assert picked == [1 + 8 * i for i in range(15)]  # 1, 9, 17, ..., 113


def test_a_pool_of_exactly_fifteen_to_twenty_nine_takes_the_first_fifteen_in_a_row():
    for size in (15, 29):
        picked, k = rt.pick_every_kth(list(range(size)), 15)
        assert k == 1 and picked == list(range(15))


def test_a_pool_smaller_than_fifteen_cannot_be_sampled():
    with pytest.raises(rt.PoolTooSmall):
        rt.pick_every_kth(list(range(14)), 15)


# ------------------------------------------------------------------ the whole selection
def test_the_selection_is_deterministic():
    rows = rows_for(POOLS)
    for policy in (None, "keep", "top-up"):
        try:
            first = rt.select(rows, set(), policy)
        except rt.PoolTooSmall:
            continue
        assert rt.select(rows, set(), policy) == first
        assert (
            rt.select(list(reversed(rows)), set(), policy) == first
        )  # input order does not matter


def test_a_year_that_is_too_small_stops_the_build_until_a_policy_is_chosen():
    with pytest.raises(rt.PoolTooSmall, match=r"2023 has 8 messages, 15 needed"):
        rt.select(rows_for(POOLS), set())
    with pytest.raises(ValueError):
        rt.select(rows_for(POOLS), set(), "guess")


def test_keep_takes_all_of_a_short_year_and_fifteen_from_the_others():
    rows = rows_for(POOLS)
    c = rt.select(rows, set(), "keep")
    assert {y: len(v) for y, v in c["by_year"].items()} == {
        "2021": 15,
        "2022": 15,
        "2023": 8,
        "2024": 15,
    }
    assert len(c["ids"]) == 53 and c["topup_ids"] == [] and c["shortfall"] == {"2023": 7}
    pools = rt.year_pools(rows, set())
    for year, k in (("2021", 40 // 15), ("2022", 31 // 15), ("2024", 20 // 15)):
        assert c["by_year"][year] == pools[year][::k][:15] and c["k_by_year"][year] == k
    assert c["by_year"]["2023"] == pools["2023"]


def test_top_up_fills_the_gap_from_the_unchosen_messages_by_the_same_style_of_rule():
    rows = rows_for(POOLS)
    c = rt.select(rows, set(), "top-up")
    assert len(c["ids"]) == 60 == len(set(c["ids"])) and c["ids"] == sorted(c["ids"])
    assert len(c["topup_ids"]) == 7
    chosen = {i for v in c["by_year"].values() for i in v}
    assert not set(c["topup_ids"]) & chosen  # extras were not already chosen
    pools = rt.year_pools(rows, set())
    leftover = sorted(i for v in pools.values() for i in v if i not in chosen)
    assert c["topup_ids"] == leftover[:: len(leftover) // 7][:7]  # k = floor(unchosen / missing)


def test_excluded_messages_never_appear():
    rows = rows_for(POOLS)
    exclude = {1000, 1001, 1002, 1050, 1090}
    for policy in ("keep", "top-up"):
        assert not set(rt.select(rows, exclude, policy)["ids"]) & exclude


def test_a_pool_that_is_big_enough_needs_no_policy():
    c = rt.select(rows_for({"2021": 30, "2022": 30, "2023": 30, "2024": 30}), set())
    assert len(c["ids"]) == 60 and c["shortfall"] == {} and c["shortfall_policy"] is None


@needs_cache
def test_on_the_real_cache_the_pools_and_the_keep_policy_are_what_the_preview_showed():
    rows = mail_cache.build_index(mail_cache.RAW_ROOT)
    spot = {int(i.removeprefix("msg")) for i in json.loads(rs.SAMPLE_PATH.read_text())["ids"]}
    pools = rt.year_pools(rows, spot)
    assert {y: len(v) for y, v in pools.items()} == {"2021": 122, "2022": 99, "2023": 8, "2024": 51}
    keep = rt.select(rows, spot, "keep")
    assert len(keep["ids"]) == 53 and not set(keep["ids"]) & spot
    assert len(rt.select(rows, spot, "top-up")["ids"]) == 60


# ------------------------------------------------------------------ privacy
def make_redactor():
    from core.claims import reader

    return reader.Redactor.from_names(["Pat Example", "Quentin Rare", "Jia Tan"], {"the", "and"})


def test_extra_names_and_handles_are_replaced_whatever_the_case_or_spacing():
    names = ["Ada Lovelace", "somehandle"]
    out, n = rt.apply_extra("Thanks to ADA lovelace and Somehandle for this.", names)
    assert out == "Thanks to [person] and [person] for this." and n == 2


def test_the_longest_extra_name_wins_over_a_shorter_one_inside_it():
    out, _ = rt.apply_extra("By Ada Lovelace Byron.", ["Ada Lovelace Byron", "Ada"])
    assert out == "By [person]."


def test_leak_check_finds_emails_urls_and_known_names_but_not_the_persona_or_diff_headers():
    r = make_redactor()
    assert rt.leaks("Contact first.last@example.org please.", r, []) == ["an email-shaped string"]
    assert rt.leaks("See https://example.org/x for more.", r, []) == ["a URL"]
    assert rt.leaks("Quentin Rare agrees.", r, []) == ["a known name"]
    assert rt.leaks("Ask somehandle.", r, ["somehandle"]) == ["a known name"]
    assert rt.leaks("Jia Tan fixed it. @@ -0,0 +1,16 @@ and @Override", r, []) == []
    assert rt.leaks("A clean sentence.", r, []) == []


def test_no_name_is_stored_in_the_repository_code():
    # The extra names live in a git-ignored file; the code only reads it.
    assert "raw" in rt.EXTRA_FILE.parts and rt.EXTRA_FILE.name == "extra_redactions.txt"
    source = (rt.Path(rt.__file__)).read_text(encoding="utf-8")
    assert "Pavlov" not in source and "Adler" not in source


# ------------------------------------------------------------------ build(): refusals
@pytest.fixture
def tmp_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "TESTSET_PATH", tmp_path / "testset.json")
    monkeypatch.setattr(rt, "SHEET_PATH", tmp_path / "sheet.csv")
    monkeypatch.setattr(rt, "GUIDE_PATH", tmp_path / "guide.md")
    return tmp_path


@needs_cache
def test_build_refuses_without_a_policy_and_writes_nothing(tmp_outputs, capsys):
    assert rt.build(None) == 2
    assert "Cannot build the test set" in capsys.readouterr().out
    assert list(tmp_outputs.iterdir()) == []


@needs_cache
def test_build_never_overwrites_a_sheet_a_person_has_started(tmp_outputs, monkeypatch, capsys):
    monkeypatch.setattr(rf, "labels_exist", lambda path=None: True)
    assert rt.build("keep") == 3
    assert "Not overwriting" in capsys.readouterr().out
    assert list(tmp_outputs.iterdir()) == []


@needs_cache
def test_build_refuses_if_the_reader_changed_after_the_freeze(tmp_outputs, monkeypatch):
    from core.claims import reader

    monkeypatch.setattr(reader, "SYSTEM_PROMPT", reader.SYSTEM_PROMPT + " Extra.")
    assert rt.build("keep") == 1
    assert list(tmp_outputs.iterdir()) == []


# ---------------------------------------------------------- build(): a real build to a temp folder
@needs_cache
def test_a_real_build_gives_a_sheet_with_empty_labels_and_a_matching_test_set(tmp_outputs):
    assert rt.build("keep") == 0
    ts = json.loads((tmp_outputs / "testset.json").read_text(encoding="utf-8"))
    assert ts["count"] == 53 and len(ts["ids"]) == 53 and ts["shortfall_policy"] == "keep"
    assert {y: len(v) for y, v in ts["ids_by_year"].items()} == {
        "2021": 15,
        "2022": 15,
        "2023": 8,
        "2024": 15,
    }
    assert not set(ts["ids"]) & set(ts["excluded_spotcheck_ids"])
    assert ts["reader_frozen_version"] == rf.load_frozen()["version"]

    raw = (tmp_outputs / "sheet.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # a BOM, so a spreadsheet program opens it as UTF-8
    with (tmp_outputs / "sheet.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [r["message_id"] for r in rows] == ts["ids"]
    assert list(rows[0]) == sheet.COLUMNS
    assert all(r[k] == "" for r in rows for k in [*sheet.KINDS, "notes"])  # no label is pre-filled
    check = sheet.check_labels(rows, ts)
    assert check.edited_text_ids == [] and not check.complete and len(check.missing) == 53

    everything = (tmp_outputs / "sheet.csv").read_text(encoding="utf-8-sig") + json.dumps(ts)
    assert not rt.EMAIL_SHAPE.search(everything) and "http" not in everything
    redactor = rs.build_redactor()
    for name in [*redactor.full_names, *redactor.tokens, *rt.load_extra_names()]:
        assert not rt.re.search(rt._name_re(name), everything), "a name reached the sheet"
    assert (tmp_outputs / "guide.md").exists()


@needs_cache
def test_a_person_can_fill_the_sheet_and_it_then_checks_out(tmp_outputs):
    assert rt.build("keep") == 0
    ts = json.loads((tmp_outputs / "testset.json").read_text(encoding="utf-8"))
    with (tmp_outputs / "sheet.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in sheet.KINDS:
            r[k] = "no"
    assert sheet.check_labels(rows, ts).complete
