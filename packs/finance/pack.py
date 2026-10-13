"""The finance pack's definition (docs/HEARTHGUARD.md §4.2). A pack provides exactly four things:

  (1) source parsers      packs/finance/parse.py (synthetic email, chat, vendor portal, ERP log)
  (2) a mapping from its records to core concepts: packs/finance/mapping.py, with the kinds below
  (3) its claim vocabulary for the Reader: CLAIM_VOCABULARY
  (4) its "normal path" definition: NORMAL_PATH

Core imports nothing from packs/. This module imports nothing from packs.oss: the finance company
must run with the OSS pack removed (eval/verify_packs.py checks that by removing it).

Choices that are the pack's, not the spec's (change them here, never in core):
  - All three privileges are sensitive: each one moves money or changes who is paid.
  - A vendor contact's change-request rights are the `vendor_edit` privilege (spec §11.1).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PrivilegeKind:
    kind: str
    sensitive: bool
    meaning: str


# §6.1: Finance privileges are vendor_edit | payment_approve | bank_change.
PRIVILEGES: tuple[PrivilegeKind, ...] = (
    PrivilegeKind("vendor_edit", True, "edit the vendor master, or submit change requests for it"),
    PrivilegeKind("payment_approve", True, "approve a payment run"),
    PrivilegeKind("bank_change", True, "change the bank details a vendor is paid to"),
)
PRIVILEGE_KINDS: tuple[str, ...] = tuple(p.kind for p in PRIVILEGES)
SENSITIVE_PRIVILEGES: tuple[str, ...] = tuple(p.kind for p in PRIVILEGES if p.sensitive)

# §6.1 Finance mapping: vendor emails, chats, portal events and ERP entries -> Action.
ACTION_KINDS: tuple[str, ...] = ("email", "chat", "portal_event", "grant", "bank_change")

# §6.1: inbox, chat channel, portal (and the ERP log) -> Place.
PLACE_KINDS: tuple[str, ...] = ("list", "chat", "portal", "tracker")

# §7.1 Bypass, finance: the bank-detail change arrived by email and not the portal, with no
# callback logged, and fewer approvers than usual. The Path properties that carry each one:
NORMAL_PATH_PROPERTIES: tuple[str, ...] = ("channel", "callback", "approvers")
NORMAL_PATH = {
    "description": "vendor portal + callback verification + two-person approval (§4.2)",
    "properties": NORMAL_PATH_PROPERTIES,
    "remembered_as": "the most common value of each property among earlier bank changes",
    "applies_to_action_kind": "bank_change",
}

# §6.1 Claim kinds, with the Reader's meaning for each in a company's finance team.
CLAIM_VOCABULARY: dict[str, str] = {
    "PRESSURE": "pushes the finance team to pay or act faster or differently",
    "URGENCY": "stresses a deadline, such as pay today or the line stops",
    "VOUCH": "endorses a person as a genuine contact at a vendor",
    "REQUESTS_PRIVILEGE": "asks to be given rights over a vendor record or payment details",
    "CAPACITY_STATEMENT": "says an approver is away, busy or unavailable",
    "CHANGE_REQUEST": "asks that vendor details, such as bank details, be changed",
    "HANDOVER_ANNOUNCEMENT": "announces that a vendor contact or an internal role has changed",
}
