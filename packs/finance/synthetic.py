"""The Northbridge Components synthetic dataset (spec §11.1). Every record is synthetic.

Run: uv run python -m packs.finance.synthetic     (writes data/synthetic/northbridge.json)

Northbridge Components is an invented mid-size manufacturer; Kestrel Metals is an invented
supplier. No real person, company, address or number appears. Addresses end in `.example`.

The record stream is scripted, not sampled, so it is the same every run. Two parts:
  - background (planted: false): the company's normal life, so a "remembered normal" exists:
    6 vendor contacts who each got change-request rights 150 to 210 days after their first
    action, 8 earlier bank-detail changes through the vendor portal with a callback and two
    approvers, a standing two-approver policy, and routine chat.
  - the planted takeover (planted: true, campaign_id 'kestrel-takeover'), dated as in §11.1.
The dates and counts of the background are choices made here to give a normal to compare with.
They are not drawn from any real company.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "northbridge.json"
CAMPAIGN = "kestrel-takeover"

CLERK = "priya.nair@northbridge.example"
CONTROLLER = "marcus.hale@northbridge.example"
LEAD = "elena.ruiz@northbridge.example"
AP_INBOX = "ap@northbridge.example"
HANNAH = "hannah.weber@kestrel-metals.example"  # a long-standing real-domain Kestrel contact
DANIEL = "daniel.cho@kestrel-meta1s.example"  # look-alike domain: digit 1 for the letter l
VOUCH_1 = "sam.ortiz@kestrel-meta1s.example"
VOUCH_2 = "lena.voss@kestrel-meta1s.example"

# (contact, vendor, first action, days from first action to change-request rights)
HISTORY_CONTACTS = (
    ("a.lindqvist@alder-fasteners.example", "alder-fasteners", "2024-01-10", 150),
    ("b.okafor@birchwood-plastics.example", "birchwood-plastics", "2024-02-05", 165),
    ("c.moreau@cobalt-castings.example", "cobalt-castings", "2024-03-12", 180),
    ("d.petrov@dunmore-coatings.example", "dunmore-coatings", "2024-04-02", 190),
    ("e.sato@elmstead-tooling.example", "elmstead-tooling", "2024-05-20", 200),
    ("f.haddad@fenwick-packaging.example", "fenwick-packaging", "2024-06-17", 210),
)
KESTREL_VENDOR = "kestrel-metals"

# Earlier bank-detail changes: (id, contact, vendor, date). Portal, callback, two approvers.
HISTORY_BANK_CHANGES = (
    ("bc-0001", HANNAH, KESTREL_VENDOR, "2024-05-14"),
    ("bc-0002", "a.lindqvist@alder-fasteners.example", "alder-fasteners", "2024-09-03"),
    ("bc-0003", "b.okafor@birchwood-plastics.example", "birchwood-plastics", "2024-10-22"),
    ("bc-0004", "c.moreau@cobalt-castings.example", "cobalt-castings", "2024-12-09"),
    ("bc-0005", "d.petrov@dunmore-coatings.example", "dunmore-coatings", "2025-02-18"),
    ("bc-0006", "e.sato@elmstead-tooling.example", "elmstead-tooling", "2025-04-01"),
    ("bc-0007", "f.haddad@fenwick-packaging.example", "fenwick-packaging", "2025-05-27"),
    ("bc-0008", HANNAH, KESTREL_VENDOR, "2025-06-24"),
)


def _t(day: str, hour: int = 10) -> str:
    return f"{day}T{hour:02d}:00:00Z"


def _plus(day: str, days: int) -> str:
    return (datetime.fromisoformat(day) + timedelta(days=days)).date().isoformat()


def _rec(source: str, rid: str, date: str, planted: bool = False, **fields) -> dict:
    out = {"source": source, "id": rid, "date": date, "synthetic": True, "planted": planted}
    out["campaign_id"] = CAMPAIGN if planted else None
    out.update(fields)
    return out


def _email(rid, date, sender, subject, body, to=(AP_INBOX,), cc=(), planted=False, vendor=None):
    return _rec(
        "email",
        rid,
        date,
        planted,
        sender=sender,
        to=list(to),
        cc=list(cc),
        subject=subject,
        body=body,
        vendor=vendor,
    )


def build() -> dict:
    recs: list[dict] = []

    # --- background: routine chat among the three employees, one post a fortnight
    day = datetime(2023, 10, 2, tzinfo=UTC)
    users = (CLERK, CONTROLLER, LEAD)
    n = 0
    while day < datetime(2025, 9, 1, tzinfo=UTC):
        n += 1
        recs.append(
            _rec(
                "chat",
                f"c-{n:04d}",
                _t(day.date().isoformat(), 9 + n % 6),
                channel="finance",
                user=users[n % 3],
                text="Routine: payment run checked.",
            )
        )
        day += timedelta(days=14)

    # --- background: standing policy and the people who may approve a bank-detail change
    recs.append(
        _rec(
            "erp",
            "pol-0001",
            _t("2023-10-01"),
            entry="policy",
            privilege="bank_change",
            approvers_required=2,
            holders=[CONTROLLER, LEAD],
        )
    )

    # --- background: six contacts, each gets change-request rights 150 to 210 days in
    for i, (contact, vendor, first, days) in enumerate(HISTORY_CONTACTS, start=1):
        recs.append(
            _email(
                f"e-h{i:02d}", _t(first), contact, "Introduction", "Introducing myself.",
                vendor=vendor,
            )
        )  # fmt: skip
        recs.append(
            _rec(
                "erp",
                f"g-h{i:02d}",
                _t(_plus(first, days)),
                entry="grant",
                actor=contact,
                privilege="vendor_edit",
                by=CONTROLLER,
                vendor=vendor,
            )
        )
    recs.append(
        _email(
            "e-h07", _t("2023-11-06"), HANNAH, "Remittance advice", "Remittance advice attached.",
            vendor=KESTREL_VENDOR,
        )
    )  # fmt: skip

    # --- background: eight earlier bank-detail changes, portal, callback, two approvers
    for rid, contact, vendor, date in HISTORY_BANK_CHANGES:
        recs.append(
            _rec(
                "portal",
                f"p-{rid}",
                _t(date),
                event="change_submitted",
                user=contact,
                vendor=vendor,
            )
        )
        recs.append(
            _rec(
                "erp",
                rid,
                _t(date, 15),
                entry="bank_change",
                actor=contact,
                vendor=vendor,
                channel="portal",
                callback_logged=True,
                approvers_required=2,
                approved_by=[CONTROLLER, LEAD],
            )
        )

    # --- the planted takeover (spec §11.1)
    recs += [
        _email(
            "e-k01", _t("2025-08-04"), DANIEL, "Hello from Kestrel Metals",
            "Hi, I am joining the Kestrel account team and will help Hannah with your orders.",
            cc=(HANNAH,), planted=True, vendor=KESTREL_VENDOR,
        ),
        _email(
            "e-k02", _t("2025-08-11"), DANIEL, "Delivery schedule",
            "Hope your week is going well! Our next delivery is on track.",
            planted=True, vendor=KESTREL_VENDOR,
        ),
        _email(
            "e-k03", _t("2025-08-20"), VOUCH_1, "Daniel",
            "Just a note that Daniel is great to work with. You can rely on him.",
            planted=True, vendor=KESTREL_VENDOR,
        ),
        _email(
            "e-k04", _t("2025-08-25"), DANIEL, "Thank you",
            "Thanks for the quick reply last time, Priya. It really helps us.",
            planted=True, vendor=KESTREL_VENDOR,
        ),
        _email(
            "e-k05", _t("2025-08-28"), VOUCH_2, "About Daniel",
            "I have worked with Daniel for years. He is the right person for your account.",
            planted=True, vendor=KESTREL_VENDOR,
        ),
        _email(
            "e-k06", _t("2025-09-02"), DANIEL, "Invoice question",
            "Quick question on invoice timing. No rush at all.",
            planted=True, vendor=KESTREL_VENDOR,
        ),
        _rec(
            "chat", "c-k01", _t("2025-09-08", 9), True, channel="finance", user=CONTROLLER,
            text="I am on leave until Sep 22.",
        ),
        _rec(
            "erp", "lv-0001", _t("2025-09-08", 9), True, entry="leave", actor=CONTROLLER,
            until=_t("2025-09-22", 9),
        ),
        _rec(
            "erp", "g-k01", _t("2025-09-15", 11), True, entry="grant", actor=DANIEL,
            privilege="vendor_edit", by=LEAD, vendor=KESTREL_VENDOR,
        ),
        _rec(
            "portal", "p-k01", _t("2025-09-15", 11), True, event="contact_added", user=DANIEL,
            vendor=KESTREL_VENDOR,
        ),
        _email(
            "e-k07", _t("2025-09-16"), DANIEL, "Urgent payment",
            "Urgent: please pay today or our line stops.", planted=True, vendor=KESTREL_VENDOR,
        ),
        _email(
            "e-k08", _t("2025-09-17", 9), DANIEL, "URGENT - pay today",
            "Urgent: pay today or the line stops. Our bank details have changed, see below.",
            planted=True, vendor=KESTREL_VENDOR,
        ),
        _rec(
            "erp", "bc-k01", _t("2025-09-17", 10), True, entry="bank_change", actor=DANIEL,
            vendor=KESTREL_VENDOR, channel="email", callback_logged=False,
            approvers_required=1, approved_by=[],
        ),
    ]  # fmt: skip

    recs.sort(key=lambda r: (r["date"], r["source"], r["id"]))
    for seq, r in enumerate(recs, start=1):
        r["seq"] = seq
    return {
        "case": "northbridge",
        "synthetic": True,
        "company": "Northbridge Components (invented)",
        "vendor": "Kestrel Metals (invented)",
        "campaign_id": CAMPAIGN,
        "records": recs,
    }


def main() -> None:
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(data['records'])} records)")


if __name__ == "__main__":
    main()
