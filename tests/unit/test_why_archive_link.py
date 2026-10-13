"""The archive link core builds for a cached mail message equals the one the pack builds."""

from core.agents import why
from packs.oss import mail_cache


def test_core_archive_link_matches_the_pack_for_msg00402():
    assert why.source_link("mail", "msg00402", None) == mail_cache.msg_url(402)
    assert mail_cache.msg_url(402).endswith("msg00402.html")


def test_core_archive_link_matches_the_pack_for_a_range_of_numbers():
    for n in (1, 512, 9999, 12345):
        assert why.source_link("mail", f"msg{n:05d}", None) == mail_cache.msg_url(n)


def test_a_stored_url_wins_over_the_archive_link():
    url = "https://example.org/stored"
    assert why.source_link("mail", "msg00402", url) == url
